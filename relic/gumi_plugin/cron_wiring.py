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

import hashlib
import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

from relic.gumi_plugin.media_state import is_media_eligible, last_media_ts

try:
    from relic.chronicle import emit_event, emit_decision, EventCategory
    from relic.persistence import PrivacyLevel
    _CHRONICLE = True
except Exception:
    _CHRONICLE = False
    EventCategory = None  # type: ignore
    PrivacyLevel = None  # type: ignore

MEDIA_COOLDOWN_DAYS = {"image": 2.0, "voice": 1.0, "music": 7.0}
_MEDIA_PROB_THRESHOLDS = {"music": 5, "voice": 30, "image": 50}  # cumulative %

ASK_COOLDOWN_HOURS = 12
ASK_DAILY_PROB_THRESHOLD = 35  # percent


_PRO_MEDIA_KEY: dict[str, str] = {
    "image": "PRO_IMAGE",
    "voice": "PRO_AUDIO",
    "music": "PRO_LYRIA",
}


def _pro_media_allowed(subject_id: str, mtype: str) -> bool:
    """Return False if subject has set the PRO_* permission for mtype to 0."""
    try:
        from relic.profile.registry import ProfileRegistry

        policy_path = ProfileRegistry()._delivery_policy_path(subject_id)
        if not policy_path.exists():
            return True
        with open(policy_path, encoding="utf-8") as fh:
            policy = json.load(fh)
        key = _PRO_MEDIA_KEY.get(mtype)
        if key is None:
            return True
        return int(policy.get(key, 2)) > 0
    except Exception:
        return True  # fail-open


def _select_ask_decision(
    subject_id: str, now: datetime, relic_home: Path | None = None
) -> tuple[bool, str | None]:
    """Decide whether this checkin should embed an open question and which topic.

    Returns (ask, topic_hint). Fail-open to (False, None) on any error.

    Gates (all must pass):
      * select_facet returns status='ask_now'
      * last checkin_exchanges.asked_at older than ASK_COOLDOWN_HOURS
      * deterministic daily roll < ASK_DAILY_PROB_THRESHOLD
    """
    try:
        if relic_home is None:
            relic_home = Path(
                os.environ.get("RELIC_HOME", "") or str(Path.home() / ".relic")
            )
        db_path = relic_home / "subjects" / subject_id / "relic.db"
        bl_path = relic_home / "subjects" / subject_id / "subject_baseline.json"
        if not db_path.exists():
            return (False, None)

        day_seed_src = f"{subject_id}|ask|{now.date()}"
        roll = int(hashlib.sha256(day_seed_src.encode()).hexdigest(), 16) % 100
        if roll >= ASK_DAILY_PROB_THRESHOLD:
            return (False, None)

        import sqlite3
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5.0)
        try:
            try:
                row = conn.execute(
                    "SELECT MAX(asked_at) FROM checkin_exchanges"
                ).fetchone()
                last_asked_iso = row[0] if row else None
            except sqlite3.OperationalError:
                last_asked_iso = None
        finally:
            conn.close()

        if last_asked_iso:
            try:
                last_dt = datetime.fromisoformat(last_asked_iso)
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=timezone.utc)
                if (now.astimezone(timezone.utc) - last_dt.astimezone(timezone.utc)).total_seconds() < ASK_COOLDOWN_HOURS * 3600:
                    return (False, None)
            except Exception:
                pass

        from relic.checkin.question_engine import select_facet
        facet_seed = int(
            hashlib.sha256(f"{subject_id}|facet|{now.date()}".encode()).hexdigest(),
            16,
        ) % (2**32)
        conn2 = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5.0)
        try:
            sel = select_facet(
                conn2,
                bl_path if bl_path.exists() else None,
                seed=facet_seed,
            )
        finally:
            conn2.close()

        if sel.get("status") != "ask_now":
            return (False, None)
        return (True, sel.get("question_hint"))
    except Exception as e:
        logger.error("ask decision failed: %s", e)
        return (False, None)


def _select_media_type(subject_id: str, hermes_home: Path, now: datetime) -> str:
    """Return 'text'|'voice'|'image'|'music'. Deterministic per subject+day."""
    policy_path = hermes_home / "workspace" / "gumi" / "media_policy.json"
    if not policy_path.exists():
        return "text"
    try:
        policy = json.loads(policy_path.read_text())
    except Exception:
        return "text"

    eligible: dict[str, bool] = {}
    for mtype in ("image", "voice", "music"):
        key = f"{mtype}_generation_enabled"
        if policy.get(key) and _pro_media_allowed(subject_id, mtype):
            eligible[mtype] = is_media_eligible(hermes_home, mtype, now, MEDIA_COOLDOWN_DAYS)

    if not any(eligible.values()):
        return "text"

    # Music floor: force if > 14 days since last generation
    if eligible.get("music"):
        last_music = last_media_ts(hermes_home, "music")
        if last_music is None or (now - last_music).days >= 14:
            return "music"

    # Deterministic daily roll
    day_seed = f"{subject_id}|media|{now.date()}"
    roll = int(hashlib.sha256(day_seed.encode()).hexdigest(), 16) % 100

    if eligible.get("music") and roll < _MEDIA_PROB_THRESHOLDS["music"]:
        return "music"
    if eligible.get("voice") and roll < _MEDIA_PROB_THRESHOLDS["voice"]:
        return "voice"
    if eligible.get("image") and roll < _MEDIA_PROB_THRESHOLDS["image"]:
        return "image"
    return "text"

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


def _subject_timezone(subject_id: str) -> Optional[Any]:
    """Return the subject's ZoneInfo from delivery_policy.json, or None."""
    try:
        import zoneinfo
        from relic.profile.registry import ProfileRegistry

        policy_path = ProfileRegistry()._delivery_policy_path(subject_id)
        if not policy_path.exists():
            return None
        with open(policy_path, encoding="utf-8") as f:
            policy = json.load(f)
        tz_str = policy.get("timezone") or policy.get("quiet_hours_timezone")
        if not tz_str and isinstance(policy.get("quiet_hours"), dict):
            tz_str = policy["quiet_hours"].get("timezone")
        if tz_str:
            return zoneinfo.ZoneInfo(tz_str)
    except Exception:
        pass
    return None


def _subject_now(subject_id: str) -> "datetime":
    """Return current datetime in the subject's configured timezone (falls back to local).

    Always returns a tz-aware datetime so callers can compare safely with
    _last_outbound_datetime without naive/aware mixing.
    """
    tz = _subject_timezone(subject_id)
    if tz:
        return datetime.now(tz)
    return datetime.now().astimezone()


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

        now = _subject_now(subject_id)
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


def _pro_checkin_allowed(subject_id: str) -> bool:
    """Return False if subject has set PRO_CHECKIN=0 (opt-out of proactive check-ins)."""
    try:
        from relic.profile.registry import ProfileRegistry

        registry = ProfileRegistry()
        policy_path = registry._delivery_policy_path(subject_id)
        if not policy_path.exists():
            return True
        with open(policy_path, encoding="utf-8") as fh:
            policy = json.load(fh)
        # PRO_CHECKIN: 0=never, 1=rarely, 2=default, 3=often, 4=maximum
        return int(policy.get("PRO_CHECKIN", 2)) > 0
    except Exception:
        return True  # fail-open: allow if unreadable


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


def _is_globally_paused() -> bool:
    """Return True if any session issued /relic pause and has not yet resumed.

    Uses is_any_session_paused() which checks ALL pause records regardless of
    session_id — required because /relic pause stores real session UUIDs, not NULL.
    Fail-open with ERROR log: DB errors return False so cron is not permanently stuck,
    but the error is visible (not silently swallowed).
    Note: single-subject system assumed — if multi-subject, this gate is cross-subject.
    """
    try:
        from relic.control.pause import PauseController

        return PauseController().is_any_session_paused()
    except Exception as exc:
        logger.error(
            "_is_globally_paused DB error — fail-open, pause may be ignored: %s", exc
        )
        return False


def _is_followup_not_due(subject_id: str, gumi_instance_id: str, hermes_profile_id: str) -> bool:
    """Check if there are no due followups for this subject."""
    service = get_continuity_service()
    due = service.due_followups(subject_id, gumi_instance_id, hermes_profile_id)
    return len(due) == 0


def _load_delivery_windows(subject_id: str) -> list[tuple[int, int, int, int]]:
    """Load delivery windows from delivery_policy.json.

    Returns list of (start_h, start_m, end_h, end_m) tuples in local time.
    Falls back to [(9,0,11,0),(19,0,21,0)] if not configured.
    """
    import re

    default = [(9, 0, 11, 0), (19, 0, 21, 0)]
    try:
        from relic.profile.registry import ProfileRegistry

        registry = ProfileRegistry()
        policy_path = registry._delivery_policy_path(subject_id)
        if not policy_path.exists():
            return default
        with open(policy_path, encoding="utf-8") as f:
            policy = json.load(f)
        raw = policy.get("delivery_windows")
        if not raw or not isinstance(raw, list):
            return default
        windows = []
        for w in raw:
            # Accept {"start": "09:00", "end": "11:00"} or "09:00-11:00"
            if isinstance(w, dict):
                s, e = w.get("start", ""), w.get("end", "")
            elif isinstance(w, str):
                parts = w.split("-", 1)
                s, e = (parts[0].strip(), parts[1].strip()) if len(parts) == 2 else ("", "")
            else:
                continue
            ms = re.match(r"^(\d{1,2}):(\d{2})$", s.strip())
            me = re.match(r"^(\d{1,2}):(\d{2})$", e.strip())
            if ms and me:
                windows.append((int(ms.group(1)), int(ms.group(2)), int(me.group(1)), int(me.group(2))))
        return windows if windows else default
    except Exception:
        return default


def _last_outbound_datetime(hermes_home: Path, subject_id: str = "") -> "datetime | None":
    """Return datetime of last outbound cron delivery in subject's timezone, or None.

    When the subject has no configured timezone, falls back to the system local
    zone so window comparisons remain consistent with _subject_now (which also
    falls back to local-aware time).
    """
    tz = _subject_timezone(subject_id) if subject_id else None
    if tz is None:
        tz = datetime.now().astimezone().tzinfo
    watermark_path = hermes_home / "state" / "memory_sync_watermark.json"
    try:
        if watermark_path.exists():
            with open(watermark_path, encoding="utf-8") as f:
                wm = json.load(f)
            mtime_ns = wm.get("last_session_mtime_ns", 0)
            if mtime_ns:
                return datetime.fromtimestamp(mtime_ns / 1e9, tz=tz)
        memory_path = hermes_home / "MEMORY.md"
        if memory_path.exists():
            return datetime.fromtimestamp(memory_path.stat().st_mtime, tz=tz)
    except Exception:
        pass
    return None


def _active_delivery_window(
    windows: list[tuple[int, int, int, int]],
    now: "datetime",
) -> "tuple[int,int,int,int] | None":
    """Return the window (sh,sm,eh,em) that contains `now`, or None."""
    for sh, sm, eh, em in windows:
        start_min = sh * 60 + sm
        end_min = eh * 60 + em
        now_min = now.hour * 60 + now.minute
        if start_min <= now_min < end_min:
            return (sh, sm, eh, em)
    return None


def _last_outbound_in_window(
    last_dt: "datetime | None",
    window: tuple[int, int, int, int],
    today: "datetime",
) -> bool:
    """Return True if the last outbound falls within `window` on the same calendar day as `today`."""
    if last_dt is None:
        return False
    if last_dt.date() != today.date():
        return False
    sh, sm, eh, em = window
    last_min = last_dt.hour * 60 + last_dt.minute
    return sh * 60 + sm <= last_min < eh * 60 + em


_RESPONSE_TIMING_FACTOR: dict[str, float] = {
    "high": 0.25,    # fires early in window (fast responder expectation)
    "medium": 0.5,   # normal midpoint
    "low": 0.85,     # fires late in window (relaxed expectation)
}


def _response_timing_factor(subject_id: str) -> float:
    """Return [0,1] position within delivery window based on response_timing_expectation.

    Reads interaction_preferences.response_timing_expectation from
    baseline_user_profile.json. Fails open to 0.5 (normal).
    """
    try:
        from relic.profile.registry import ProfileRegistry

        registry = ProfileRegistry()
        profile = registry.get_subject(subject_id)
        if profile is None:
            return 0.5
        baseline_path = profile.relic_subject_home / "baseline_user_profile.json"
        if not baseline_path.exists():
            return 0.5
        with open(baseline_path, encoding="utf-8") as fh:
            baseline = json.load(fh)
        value = (
            baseline.get("interaction_preferences", {}).get("response_timing_expectation")
            or baseline.get("response_timing_expectation")
        )
        return _RESPONSE_TIMING_FACTOR.get(str(value).lower(), 0.5)
    except Exception:
        return 0.5


def _window_jitter_minute(subject_id: str, window: tuple[int, int, int, int], date: "datetime") -> int:
    """Return today's target send-minute (absolute, local time) within the window.

    Seeded by subject + window + date so it is stable within a day but varies
    across days.  The offset stays at least 30 min from the window end so
    cron has room to catch it.  Minimum jitter range: 30 min per window.

    response_timing_expectation shifts the target position within the window:
    - high  → early quarter  (subject expects fast responses)
    - medium → midpoint (default)
    - low   → late quarter (subject is relaxed about timing)
    """
    import hashlib

    sh, sm, eh, em = window
    start_min = sh * 60 + sm
    end_min = eh * 60 + em
    # Reserve 30 min before window end so the message can actually fire
    available = max(end_min - start_min - 30, 0)

    # Base deterministic offset from hash
    seed = f"{subject_id}|{window}|{date.strftime('%Y-%m-%d')}"
    h = int(hashlib.sha256(seed.encode()).hexdigest(), 16)
    base_offset = h % (available + 1)

    # Shift offset toward timing preference (blended 50/50 with hash for stability)
    timing_factor = _response_timing_factor(subject_id)
    preferred_offset = int(available * timing_factor)
    blended_offset = (base_offset + preferred_offset) // 2

    return start_min + min(blended_offset, available)


def _is_delivery_window_open(subject_id: str, hermes_home: Path) -> bool:
    """Return True if now is inside a delivery window, past today's jitter minute, and not yet sent."""
    now = _subject_now(subject_id)
    windows = _load_delivery_windows(subject_id)
    active = _active_delivery_window(windows, now)
    if active is None:
        return False  # outside all windows
    last_dt = _last_outbound_datetime(hermes_home, subject_id)
    if _last_outbound_in_window(last_dt, active, now):
        return False  # already sent in this window today
    # Check jitter: only fire once we've reached today's randomised target minute
    target_min = _window_jitter_minute(subject_id, active, now)
    now_min = now.hour * 60 + now.minute
    if now_min < target_min:
        return False  # too early within the window — wait for next tick
    return True


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

    # Check /relic pause — user-initiated global pause
    if _is_globally_paused():
        reasons.append(RuntimeDecisionReason.subject_paused)
        return RuntimeDecision.NO_REPLY, reasons, None

    # Check PRO_CHECKIN permission — respect subject opt-out
    if not _pro_checkin_allowed(subject_id):
        reasons.append(RuntimeDecisionReason.subject_paused)
        return RuntimeDecision.NO_REPLY, reasons, None

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

    # Check for due followups — used to determine CANDIDATE vs DELIVER vs NO_REPLY
    _svc = get_continuity_service()
    _due = _svc.due_followups(subject_id, gumi_instance_id, hermes_profile_id)

    # Delivery window gate: fire only inside a configured time window,
    # past today's jitter offset, and only once per window per day.
    hermes_home_str = os.environ.get("HERMES_HOME", "")
    hermes_home = Path(hermes_home_str) if hermes_home_str else Path.home() / ".hermes"

    if not _is_delivery_window_open(subject_id, hermes_home):
        if _due:
            # Due work is ready but delivery window is closed → CANDIDATE (awaits gate)
            reasons.append(RuntimeDecisionReason.no_due_work)
            _msg = _due[0].get("message", "")
            return RuntimeDecision.CANDIDATE, reasons, {"message": _msg}
        reasons.append(RuntimeDecisionReason.followup_not_due)
        return RuntimeDecision.NO_REPLY, reasons, None

    reasons.append(RuntimeDecisionReason.no_due_work)  # reuse existing enum value
    now_dt = _subject_now(subject_id)
    now_str = now_dt.strftime("%H:%M %Z")
    media_type = _select_media_type(subject_id, hermes_home, now_dt)
    ask, ask_topic = _select_ask_decision(subject_id, now_dt)
    msg = f"DELIVER\ntipo: {media_type}\nora: {now_str}"
    if ask and ask_topic:
        msg += f"\nask: true\nask_topic: {ask_topic}"
    return RuntimeDecision.DELIVER, reasons, {"message": msg}


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

    if _CHRONICLE:
        try:
            metadata = {"source": "no_agent_cron"}
            emit_event(
                event_type="cron_decision",
                event_category=EventCategory.DECISION,
                source_module="relic.gumi_plugin.cron_wiring",
                subject_id=subject_id,
                profile_id=hermes_profile_id,
                hermes_profile_id=hermes_profile_id,
                payload={
                    "decision": decision.value if hasattr(decision, "value") else str(decision),
                    "reason_codes": [r.value if hasattr(r, "value") else str(r) for r in reason_codes] if reason_codes else [],
                    "source": metadata.get("source", "no_agent_cron"),
                },
            )
            emit_decision(
                decision_kind="cron_evaluator",
                selected_action={"decision": decision.value if hasattr(decision, "value") else str(decision)},
                actor_type="rule",
                actor_id="cron_evaluator",
                subject_id=subject_id,
                rationale_summary=(f"Cron decision: {','.join(r.value if hasattr(r, 'value') else str(r) for r in reason_codes) if reason_codes else 'ok'}")[:280],
            )
        except Exception:
            pass


def make_decision(
    subject_id: str,
    gumi_instance_id: str,
    hermes_profile_id: str,
    force: bool = False,
) -> tuple[RuntimeDecision, list[RuntimeDecisionReason], Optional[dict]]:
    """Make a runtime decision for the given subject.

    This is the main entry point for the no-agent cron script.

    Args:
        force: Skip delivery window and jitter checks — bypass all gates except
               quiet hours and subject pause. Useful for manual testing.

    Returns:
        Tuple of (decision, reason_codes, candidate_data)
    """
    if _CHRONICLE:
        try:
            emit_event(
                event_type="cron_fired",
                event_category=EventCategory.BACKGROUND,
                source_module="relic.gumi_plugin.cron_wiring",
                subject_id=subject_id,
                profile_id=hermes_profile_id,
                payload={"trigger": "make_decision"},
            )
        except Exception:
            pass
    if force:
        reasons = [RuntimeDecisionReason.no_due_work]
        hermes_home_str = os.environ.get("HERMES_HOME", "")
        hermes_home = Path(hermes_home_str) if hermes_home_str else Path.home() / ".hermes"
        now_dt = _subject_now(subject_id)
        now_str = now_dt.strftime("%H:%M %Z")
        # RELIC_FORCE_MEDIA_TYPE overrides the normal probabilistic media selection
        forced_media = os.environ.get("RELIC_FORCE_MEDIA_TYPE", "").strip().lower()
        if forced_media in ("voice", "image", "music", "text"):
            media_type = forced_media
        else:
            media_type = _select_media_type(subject_id, hermes_home, now_dt)
        ask, ask_topic = _select_ask_decision(subject_id, now_dt)
        msg = f"DELIVER\ntipo: {media_type}\nora: {now_str} [FORCE]"
        if ask and ask_topic:
            msg += f"\nask: true\nask_topic: {ask_topic}"
        return RuntimeDecision.DELIVER, reasons, {"message": msg}
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
    import relic as _relic
    relic_root = str(Path(_relic.__file__).parent.parent)
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

SUBJECT_ID="${{1:-${{RELIC_SUBJECT_ID:-}}}}"
GUMI_INSTANCE_ID="${{2:-${{RELIC_GUMI_INSTANCE_ID:-$SUBJECT_ID}}}}"
HERMES_PROFILE_ID="${{3:-${{RELIC_HERMES_PROFILE_ID:-${{GUMI_HERMES_PROFILE_NAME:-}}}}}}"

if [[ -z "$SUBJECT_ID" ]]; then
    echo "ERROR: subject_id required (set RELIC_SUBJECT_ID or pass as arg)" >&2
    exit 1
fi

# Call the Python decision logic via this inline script. Default to the
# interpreter that generated the script so test/venv dependencies are preserved.
FORCE_DELIVER="${{4:-}}"
RELIC_PYTHON="${{RELIC_PYTHON:-{sys.executable}}}"
"$RELIC_PYTHON" - "$SUBJECT_ID" "$GUMI_INSTANCE_ID" "$HERMES_PROFILE_ID" "$FORCE_DELIVER" <<'PYTHON_EOF'
import json
import os
import sys
from pathlib import Path

# Add relic to path (hardcoded at script generation time — __file__ is '-' in heredoc)
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))  # fallback
sys.path.insert(0, '{relic_root}')  # reliable absolute path

from relic.gumi_plugin.cron_wiring import make_decision, emit_decision_event
from relic.hermes_runtime import RuntimeDecision

subject_id = sys.argv[1] if len(sys.argv) > 1 else ""
gumi_instance_id = sys.argv[2] if len(sys.argv) > 2 else ""
hermes_profile_id = sys.argv[3] if len(sys.argv) > 3 else ""
force = (
    (sys.argv[4].strip().lower() in ("--force", "force", "1", "true") if len(sys.argv) > 4 else False)
    or os.environ.get("RELIC_FORCE_CHECKIN", "").lower() in ("1", "true", "yes")
)

if not subject_id:
    print("ERROR: subject_id required", file=sys.stderr)
    sys.exit(1)

try:
    decision, reasons, candidate_data = make_decision(
        subject_id=subject_id,
        gumi_instance_id=gumi_instance_id,
        hermes_profile_id=hermes_profile_id,
        force=force,
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
        if candidate_data and "message" in candidate_data:
            print(candidate_data["message"])
        _hermes_home = os.environ.get("HERMES_HOME", "")
        if _hermes_home:
            from relic.checkin.context_builder import build_deliver_context
            _relic_home_env = os.environ.get("RELIC_HOME", "") or str(Path.home() / ".relic")
            _ctx = build_deliver_context(
                subject_id,
                Path(_hermes_home),
                Path(_relic_home_env),
            )
            if _ctx:
                print(_ctx)
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
    hermes_home: Optional[str] = None,
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
    if hermes_home:
        scripts_base = Path(hermes_home) / "scripts" / subject_id
    else:
        scripts_base = Path("~/.hermes/scripts").expanduser() / subject_id
    scripts_base.mkdir(parents=True, exist_ok=True)

    decision_types = ["checkin", "followup", "proactivity"]
    scripts: dict[str, Path] = {}
    hermes_commands: list[str] = []

    # Write the memory sync script
    sync_script_path = scripts_base / "relic_memory_sync.sh"
    sync_script_content = render_memory_sync_script()
    sync_script_path.write_text(sync_script_content, encoding="utf-8")
    sync_script_path.chmod(0o700)
    scripts["memory_sync"] = sync_script_path

    if dry_run:
        hermes_commands.append(
            f"hermes cron create --no-agent --script {sync_script_path} "
            f'"2-59/30 * * * *" --name gumi_memory_sync_{subject_id}'
        )

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

            _hermes_home = hermes_home or os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))
            run_env = os.environ.copy()
            run_env["HERMES_HOME"] = _hermes_home

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


# ---------------------------------------------------------------------------
# Memory sync script
# ---------------------------------------------------------------------------

def render_checkin_delivery_script() -> str:
    """Render the post-LLM delivery wrapper script for checkin_message cron job.

    Hermes passes the LLM output via stdin. This script delegates to
    checkin_media_dispatcher which handles text/voice/image/music dispatch.
    """
    return '''#!/usr/bin/env bash
# Hermes checkin delivery post-processor for Relic
# Generated by cron_wiring.py - do not edit manually
#
# Reads LLM output from stdin, dispatches media or text via checkin_media_dispatcher.

set -euo pipefail

LLM_OUTPUT=$(cat)

exec python3 -m relic.gumi_plugin.checkin_media_dispatcher \\
  --llm-output "$LLM_OUTPUT" \\
  --hermes-home "${HERMES_HOME:-$HOME/.hermes}" \\
  --subject-home "${RELIC_SUBJECT_HOME:-}" \\
  --subject-id "${RELIC_SUBJECT_ID:-}"
'''


def render_checkin_dispatch_script(subject_id: str) -> str:
    """Render the no-agent dispatch script that reads latest checkin_message output
    and routes it through checkin_media_dispatcher.

    Reads from Hermes cron output dir: $HERMES_HOME/cron/output/{subject_id}_checkin_message/
    Skips if no file modified within the last 8 minutes (job runs every 30 min, allow slack).
    """
    import relic as _relic
    from pathlib import Path as _Path
    relic_root = str(_Path(_relic.__file__).parent.parent)
    return f'''#!/usr/bin/env bash
# Hermes no-agent checkin dispatch script for Relic
# Generated by cron_wiring.py - do not edit manually
#
# Reads latest LLM checkin output and dispatches media via checkin_media_dispatcher.

set -euo pipefail

SUBJECT_ID="${{RELIC_SUBJECT_ID:-{subject_id}}}"
HERMES_HOME="${{HERMES_HOME:-$HOME/.hermes}}"
RELIC_PYTHON="${{RELIC_PYTHON:-{sys.executable}}}"
OUTPUT_DIR="$HERMES_HOME/cron/output/${{SUBJECT_ID}}_checkin_message"

if [ ! -d "$OUTPUT_DIR" ]; then
    exit 0
fi

# Find most recent .md file, modified within last 8 minutes
LATEST=$(find "$OUTPUT_DIR" -name "*.md" -mmin -8 2>/dev/null | sort -rV | head -1)

if [ -z "$LATEST" ]; then
    exit 0
fi

# Skip [SILENT] responses
if grep -q '^\\[SILENT\\]' "$LATEST" 2>/dev/null; then
    exit 0
fi

FORCE="${{RELIC_FORCE_CHECKIN:-}}"
FORCE_FLAG=""
if [ "$FORCE" = "1" ] || [ "$FORCE" = "true" ] || [ "$FORCE" = "yes" ]; then
    FORCE_FLAG="--force"
fi

RELIC_SUBJECT_HOME="${{RELIC_SUBJECT_HOME:-$HOME/.relic/subjects/$SUBJECT_ID}}"

"$RELIC_PYTHON" - "$LATEST" "$HERMES_HOME" "$RELIC_SUBJECT_HOME" "$SUBJECT_ID" "${{FORCE_FLAG:-}}" <<'PYEOF'
import sys
sys.path.insert(0, '{relic_root}')
from pathlib import Path
from relic.gumi_plugin.checkin_media_dispatcher import dispatch

llm_output_file = sys.argv[1]
hermes_home = Path(sys.argv[2])
relic_subject_home = Path(sys.argv[3])
subject_id = sys.argv[4]
force = "--force" in sys.argv[5:]

llm_output = Path(llm_output_file).read_text(encoding="utf-8").strip()
if not llm_output or llm_output == "[SILENT]":
    sys.exit(0)

dispatch(
    llm_output=llm_output,
    hermes_home=hermes_home,
    relic_subject_home=relic_subject_home,
    subject_id=subject_id,
    force=force,
)
PYEOF
'''


def render_memory_sync_script() -> str:
    """Render the memory sync shell script content for gumi_memory_sync cron job."""
    import relic as _relic
    from pathlib import Path as _Path
    relic_root = str(_Path(_relic.__file__).parent.parent)
    return f'''#!/usr/bin/env bash
# Hermes no-agent memory sync script for Relic
# Generated by cron_wiring.py - do not edit manually
#
# Scans session JSONs and syncs outbound messages into MEMORY.md

set -euo pipefail

HERMES_PROFILE_ID="${{RELIC_HERMES_PROFILE_ID:-${{GUMI_HERMES_PROFILE_NAME:-}}}}"
RELIC_PYTHON="${{RELIC_PYTHON:-{sys.executable}}}"

exec "$RELIC_PYTHON" -c "
import sys
sys.path.insert(0, '{relic_root}')
from relic.gumi_plugin.memory_sync import main
main()
" --hermes-home "${{HERMES_HOME:-$HOME/.hermes}}"
'''
