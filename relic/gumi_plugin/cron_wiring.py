"""Hermes no-agent cron wiring (FIX02).

This module wires the Hermes no-agent cron provisioning to Relic decision logic.
It creates a shell script that runs on a cron schedule and emits RuntimeDecision
values based on continuity follow-up state.

NO_REPLY: empty stdout + decision event
CANDIDATE: candidate message to stdout (delivery gate required)
DELIVER: deliver message to stdout after sanitizer + delivery gate
BLOCKED/ERROR: audit event only
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from relic.hermes_runtime import (
    DecisionEvent,
    RuntimeDecision,
    RuntimeDecisionReason,
)
from relic.shared_continuity.service import ContinuityService, get_continuity_service

# Path to the no-agent decision script consumed by Hermes cron. Keep this
# unexpanded so tests and callers that override HOME get an isolated path.
NO_AGENT_SCRIPT_PATH = Path("~/.hermes/scripts/relic_no_agent_decision.sh")

# Default cron schedule for no-agent probe (every 30 minutes)
DEFAULT_NO_AGENT_CRON_SCHEDULE = "*/30 * * * *"


def _is_quiet_hours(subject_id: str) -> bool:
    """Check if current time is within quiet hours for the subject."""
    try:
        from relic.profile.registry import ProfileRegistry

        registry = ProfileRegistry()
        policy_path = registry._delivery_policy_path(subject_id)
        if not policy_path.exists():
            return False

        import json

        with open(policy_path) as f:
            policy = json.load(f)

        quiet_hours = policy.get("quiet_hours", "")
        if not quiet_hours:
            return False

        # Parse "HH:MM-HH:MM" format (e.g., "22:00-08:00")
        if "-" not in quiet_hours:
            return False

        start_str, end_str = quiet_hours.split("-", 1)
        start_hour, start_min = int(start_str.split(":")[0]), int(start_str.split(":")[1])
        end_hour, end_min = int(end_str.split(":")[0]), int(end_str.split(":")[1])

        now = datetime.now(timezone.utc)
        current_minutes = now.hour * 60 + now.minute
        start_minutes = start_hour * 60 + start_min
        end_minutes = end_hour * 60 + end_min

        if start_minutes <= end_minutes:
            # Same day range (e.g., 09:00-17:00)
            return start_minutes <= current_minutes <= end_minutes
        else:
            # Overnight range (e.g., 22:00-08:00)
            return current_minutes >= start_minutes or current_minutes <= end_minutes
    except Exception:
        return False


def _is_platform_not_allowlisted(subject_id: str) -> bool:
    """Check if the delivery platform is not allowlisted for active elicitation."""
    try:
        from relic.profile.registry import ProfileRegistry

        registry = ProfileRegistry()
        policy_path = registry._delivery_policy_path(subject_id)
        if not policy_path.exists():
            return True

        import json

        with open(policy_path) as f:
            policy = json.load(f)

        # If consent_for_active_elicitation is False, platform is effectively not allowlisted
        return not policy.get("consent_for_active_elicitation", False)
    except Exception:
        return False


def _is_subject_paused(subject_id: str) -> bool:
    """Check if the subject is globally paused."""
    try:
        from relic.profile.registry import ProfileRegistry

        registry = ProfileRegistry()
        profile = registry.get_subject(subject_id)
        if profile is None:
            return False

        # Subject is paused if status is not active
        return profile.status != "active"
    except Exception:
        return False


def _is_continuity_scope_paused(subject_id: str) -> bool:
    """Check if the continuity scope is paused for this subject."""
    service = get_continuity_service()
    # Check global scope pause via the _scopes dict
    scope_key = f"{subject_id}:{None}:{None}:global"
    return service._scopes.get(scope_key, {}).get("is_paused", False)


def _is_followup_not_due(subject_id: str, gumi_instance_id: str, hermes_profile_id: str) -> bool:
    """Check if there are no due followups for this subject."""
    service = get_continuity_service()
    due = service.due_followups(subject_id, gumi_instance_id, hermes_profile_id)
    return len(due) == 0


def _is_followup_expired(subject_id: str, gumi_instance_id: str, hermes_profile_id: str) -> bool:
    """Check if all followups for this subject have expired."""
    service = get_continuity_service()
    due = service.due_followups(subject_id, gumi_instance_id, hermes_profile_id)
    # If no due followups, consider it not expired (no work to expire)
    return False


def _is_followup_max_attempts_reached(subject_id: str, gumi_instance_id: str, hermes_profile_id: str) -> bool:
    """Check if max attempts have been reached for all followups."""
    service = get_continuity_service()
    due = service.due_followups(subject_id, gumi_instance_id, hermes_profile_id)
    # If no due followups, max attempts hasn't blocked us
    if not due:
        return False

    # Check if all due followups have exhausted attempts
    return all(f.get("attempt_count", 0) >= f.get("max_attempts", 0) for f in due)


def _is_followup_delivery_allowed(
    subject_id: str,
    gumi_instance_id: str,
    hermes_profile_id: str,
) -> bool:
    """Return whether a due follow-up may be emitted as a delivery-gated candidate."""
    return not _is_platform_not_allowlisted(subject_id)


def _evaluate_decision(
    subject_id: str,
    gumi_instance_id: str,
    hermes_profile_id: str,
) -> tuple[RuntimeDecision, list[RuntimeDecisionReason], Optional[dict]]:
    """Evaluate the runtime decision for a subject.

    Returns:
        Tuple of (decision, reason_codes, candidate_data)
        candidate_data is a dict with 'message' key for CANDIDATE/DELIVER, None otherwise.
    """
    reasons: list[RuntimeDecisionReason] = []

    # Check quiet hours
    if _is_quiet_hours(subject_id):
        reasons.append(RuntimeDecisionReason.quiet_hours)
        return RuntimeDecision.BLOCKED, reasons, None

    # Check platform not allowlisted
    if _is_platform_not_allowlisted(subject_id):
        reasons.append(RuntimeDecisionReason.platform_not_allowlisted)
        return RuntimeDecision.BLOCKED, reasons, None

    # Check subject paused
    if _is_subject_paused(subject_id):
        reasons.append(RuntimeDecisionReason.subject_paused)
        return RuntimeDecision.BLOCKED, reasons, None

    # Check continuity scope paused
    if _is_continuity_scope_paused(subject_id):
        reasons.append(RuntimeDecisionReason.continuity_scope_paused)
        return RuntimeDecision.BLOCKED, reasons, None

    # Check followup not due
    if _is_followup_not_due(subject_id, gumi_instance_id, hermes_profile_id):
        reasons.append(RuntimeDecisionReason.followup_not_due)
        return RuntimeDecision.NO_REPLY, reasons, None

    # Check followup expired
    if _is_followup_expired(subject_id, gumi_instance_id, hermes_profile_id):
        reasons.append(RuntimeDecisionReason.followup_expired)
        return RuntimeDecision.BLOCKED, reasons, None

    # Check followup max attempts
    if _is_followup_max_attempts_reached(subject_id, gumi_instance_id, hermes_profile_id):
        reasons.append(RuntimeDecisionReason.followup_max_attempts_reached)
        return RuntimeDecision.BLOCKED, reasons, None

    # All gates passed - we have a CANDIDATE
    # Note: DELIVER requires additional sanitizer + delivery gate which is
    # handled by the caller after this function returns CANDIDATE
    service = get_continuity_service()
    due = service.due_followups(subject_id, gumi_instance_id, hermes_profile_id)

    if due:
        # Check delivery gate BEFORE returning CANDIDATE
        if not _is_followup_delivery_allowed(subject_id, gumi_instance_id, hermes_profile_id):
            reasons.append(RuntimeDecisionReason.platform_not_allowlisted)
            return RuntimeDecision.BLOCKED, reasons, None

        candidate_data = {
            "message": f"Continuity follow-up due for subject {subject_id}",
            "followups": due,
        }
        return RuntimeDecision.CANDIDATE, reasons, candidate_data

    # No due work
    reasons.append(RuntimeDecisionReason.no_due_work)
    return RuntimeDecision.NO_REPLY, reasons, None


def emit_decision_event(
    decision: RuntimeDecision,
    reason_codes: list[RuntimeDecisionReason],
    subject_id: str,
    gumi_instance_id: str,
    hermes_profile_id: str,
    target_id: Optional[str] = None,
) -> None:
    """Emit a DecisionEvent for audit purposes."""
    event = DecisionEvent(
        decision=decision,
        reason_codes=reason_codes,
        subject_id=subject_id,
        gumi_instance_id=gumi_instance_id,
        hermes_profile_id=hermes_profile_id,
        target_id=target_id,
        metadata={"source": "no_agent_cron"},
    )

    # Write event to a log file for audit
    event_log_path = Path("~/.relic/decision_events.jsonl").expanduser()
    event_log_path.parent.mkdir(parents=True, exist_ok=True)

    with open(event_log_path, "a") as f:
        f.write(json.dumps(event.to_dict()) + "\n")


def make_decision(
    subject_id: str,
    gumi_instance_id: str,
    hermes_profile_id: str,
) -> tuple[RuntimeDecision, list[RuntimeDecisionReason], Optional[dict]]:
    """Make a runtime decision for the given subject.

    This is the main entry point for the no-agent cron script.

    Returns:
        Tuple of (decision, reason_codes, candidate_data)
    """
    return _evaluate_decision(subject_id, gumi_instance_id, hermes_profile_id)


def render_no_agent_script(script_path: Path) -> str:
    """Render the no-agent decision shell script content.

    This script is consumed by Hermes cron. It:
    1. Accepts subject_id as argument
    2. Queries ContinuityService.due_followups()
    3. Returns RuntimeDecision enum value via stdout
    4. NO_REPLY: exit 0 with empty stdout
    5. CANDIDATE: stdout with candidate text, exit 0
    6. DELIVER: stdout with deliver text, exit 0
    7. BLOCKED/ERROR: no stdout, exit 0 (audit event only)
    """
    return f'''#!/usr/bin/env bash
# Hermes no-agent cron decision script for Relic
# Generated by cron_wiring.py - do not edit manually
#
# Usage: {script_path.name} <subject_id> <gumi_instance_id> <hermes_profile_id>
#
# Exit codes:
#   0 - decision emitted successfully (NO_REPLY, CANDIDATE, or DELIVER)
#   1 - error
#
# stdout:
#   NO_REPLY  - empty
#   CANDIDATE - candidate message text
#   DELIVER   - deliver message text
#   BLOCKED   - empty (audit event only)
#   ERROR     - empty (audit event only)

set -euo pipefail

SUBJECT_ID="${{1:-}}"
GUMI_INSTANCE_ID="${{2:-}}"
HERMES_PROFILE_ID="${{3:-}}"

if [[ -z "$SUBJECT_ID" ]]; then
    echo "ERROR: subject_id required" >&2
    exit 1
fi

# Call the Python decision logic via this inline script. Default to the
# interpreter that generated the script so test/venv dependencies are preserved.
RELIC_PYTHON="${{RELIC_PYTHON:-{sys.executable}}}"
"$RELIC_PYTHON" - "$SUBJECT_ID" "$GUMI_INSTANCE_ID" "$HERMES_PROFILE_ID" <<'PYTHON_EOF'
import json
import sys
from pathlib import Path

# Add relic to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from relic.gumi_plugin.cron_wiring import make_decision, emit_decision_event
from relic.hermes_runtime import RuntimeDecision

subject_id = sys.argv[1] if len(sys.argv) > 1 else ""
gumi_instance_id = sys.argv[2] if len(sys.argv) > 2 else ""
hermes_profile_id = sys.argv[3] if len(sys.argv) > 3 else ""

if not subject_id:
    print("ERROR: subject_id required", file=sys.stderr)
    sys.exit(1)

try:
    decision, reasons, candidate_data = make_decision(
        subject_id=subject_id,
        gumi_instance_id=gumi_instance_id,
        hermes_profile_id=hermes_profile_id,
    )

    # Emit decision event for audit
    emit_decision_event(
        decision=decision,
        reason_codes=reasons,
        subject_id=subject_id,
        gumi_instance_id=gumi_instance_id,
        hermes_profile_id=hermes_profile_id,
    )

    if decision == RuntimeDecision.NO_REPLY:
        # Empty stdout, exit 0
        sys.exit(0)
    elif decision == RuntimeDecision.CANDIDATE:
        # Emit candidate message - delivery gate required before actual delivery
        if candidate_data and "message" in candidate_data:
            print(candidate_data["message"])
        sys.exit(0)
    elif decision == RuntimeDecision.DELIVER:
        # Emit deliver message after sanitizer + delivery gate
        if candidate_data and "message" in candidate_data:
            print(candidate_data["message"])
        sys.exit(0)
    else:
        # BLOCKED or ERROR - no stdout, exit 0
        sys.exit(0)

except Exception as e:
    print(f"ERROR: {{e}}", file=sys.stderr)
    sys.exit(1)
PYTHON_EOF
'''


def provision_no_agent_cron(
    subject_id: str,
    gumi_instance_id: str,
    hermes_profile_id: str,
    schedule: str = DEFAULT_NO_AGENT_CRON_SCHEDULE,
    dry_run: bool = True,
    script_path: Path | None = None,
) -> dict:
    """Provision the no-agent cron job for a subject.

    Creates the shell script at NO_AGENT_SCRIPT_PATH and optionally registers
    it with Hermes via 'hermes cron create --no-agent --script <path>'.

    Args:
        subject_id: The subject identifier
        gumi_instance_id: The Gumi instance identifier
        hermes_profile_id: The Hermes profile identifier
        schedule: Cron schedule expression (default: every 30 minutes)
        dry_run: If True, only create the script without registering with Hermes

    Returns:
        dict with keys:
            script_path: Path to the created script
            hermes_command: The hermes cron create command (if not dry_run)
            returncode: Return code from hermes command (if not dry_run)
            stdout: stdout from hermes command (if not dry_run)
            stderr: stderr from hermes command (if not dry_run)
    """
    script_path = script_path or NO_AGENT_SCRIPT_PATH.expanduser()
    script_path.parent.mkdir(parents=True, exist_ok=True)

    # Render and write the script
    script_content = render_no_agent_script(script_path)
    script_path.write_text(script_content, encoding="utf-8")
    script_path.chmod(0o755)

    result = {
        "script_path": str(script_path),
        "subject_id": subject_id,
        "schedule": schedule,
        "dry_run": dry_run,
    }

    if dry_run:
        result["hermes_command"] = (
            f"hermes cron create --no-agent --script {script_path} "
            f'"{schedule}" --name relic_no_agent_{subject_id}'
        )
        return result

    # Register with Hermes
    hermes_bin = subprocess.run(
        ["which", "hermes"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()

    if not hermes_bin:
        raise FileNotFoundError("hermes command not found in PATH")

    # Build environment
    hermes_home = os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))
    run_env = os.environ.copy()
    run_env["HERMES_HOME"] = hermes_home

    # Run hermes cron create
    cmd = [
        hermes_bin,
        "cron",
        "create",
        "--no-agent",
        "--script",
        str(script_path),
        schedule,
        "--name",
        f"relic_no_agent_{subject_id}",
    ]

    proc = subprocess.run(
        cmd,
        env=run_env,
        capture_output=True,
        text=True,
        timeout=60,
    )

    result["hermes_command"] = " ".join(cmd)
    result["returncode"] = proc.returncode
    result["stdout"] = proc.stdout.strip()[:500]
    result["stderr"] = proc.stderr.strip()[:500]

    if proc.returncode != 0:
        raise RuntimeError(
            f"hermes cron create failed for {subject_id} "
            f"with exit code {proc.returncode}: {proc.stderr}"
        )

    return result


def provision_for_subject(
    subject_id: str,
    gumi_instance_id: str,
    hermes_profile_id: str,
    schedule: str = DEFAULT_NO_AGENT_CRON_SCHEDULE,
    dry_run: bool = True,
) -> dict:
    """Provision subject-specific no-agent cron jobs for check-in, follow-up, and proactivity decisions.

    Creates three separate shell scripts (one per decision type) under
    ~/.hermes/scripts/<subject_id>/ and optionally registers them with Hermes.

    Args:
        subject_id: The subject identifier.
        gumi_instance_id: The Gumi instance identifier.
        hermes_profile_id: The Hermes profile identifier.
        schedule: Cron schedule expression (default: every 30 minutes).
        dry_run: If True, only create scripts without registering with Hermes.

    Returns:
        dict with keys:
            scripts: dict mapping decision type to script path
            hermes_commands: list of hermes cron create commands (if not dry_run)
            returncode: Return code from hermes command (if not dry_run)
            stdout: stdout from hermes command (if not dry_run)
            stderr: stderr from hermes command (if not dry_run)
    """
    scripts_base = Path("~/.hermes/scripts").expanduser() / subject_id
    scripts_base.mkdir(parents=True, exist_ok=True)

    decision_types = ["checkin", "followup", "proactivity"]
    scripts: dict[str, Path] = {}
    hermes_commands: list[str] = []

    for dtype in decision_types:
        script_path = scripts_base / f"relic_{dtype}_decision.sh"
        script_content = render_no_agent_script(script_path)
        # Override the name suffix to be type-specific
        script_content = script_content.replace(
            f"relic_no_agent_{subject_id}",
            f"relic_no_agent_{dtype}_{subject_id}",
        )
        script_path.write_text(script_content, encoding="utf-8")
        script_path.chmod(0o755)
        scripts[dtype] = script_path

        if dry_run:
            hermes_commands.append(
                f"hermes cron create --no-agent --script {script_path} "
                f'"{schedule}" --name relic_no_agent_{dtype}_{subject_id}'
            )
        else:
            # Register with Hermes
            hermes_bin = subprocess.run(
                ["which", "hermes"],
                capture_output=True,
                text=True,
                check=False,
            ).stdout.strip()
            if not hermes_bin:
                raise FileNotFoundError("hermes command not found in PATH")

            hermes_home = os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))
            run_env = os.environ.copy()
            run_env["HERMES_HOME"] = hermes_home

            cmd = [
                hermes_bin,
                "cron",
                "create",
                "--no-agent",
                "--script",
                str(script_path),
                schedule,
                "--name",
                f"relic_no_agent_{dtype}_{subject_id}",
            ]
            proc = subprocess.run(
                cmd,
                env=run_env,
                capture_output=True,
                text=True,
                timeout=60,
            )
            hermes_commands.append(" ".join(cmd))
            if proc.returncode != 0:
                raise RuntimeError(
                    f"hermes cron create failed for {dtype} of {subject_id} "
                    f"with exit code {proc.returncode}: {proc.stderr}"
                )

    result: dict[str, Any] = {
        "scripts": {k: str(v) for k, v in scripts.items()},
        "subject_id": subject_id,
        "gumi_instance_id": gumi_instance_id,
        "hermes_profile_id": hermes_profile_id,
        "schedule": schedule,
        "dry_run": dry_run,
        "hermes_commands": hermes_commands,
    }

    if not dry_run:
        result["returncode"] = proc.returncode
        result["stdout"] = proc.stdout.strip()[:500]
        result["stderr"] = proc.stderr.strip()[:500]

    return result
