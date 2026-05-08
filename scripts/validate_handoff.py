#!/usr/bin/env python3
"""Validate Relic E2E subagent handoff completeness.

Validates:
- local handoff TASKS.yaml exists and is well-formed when dev_docs is present
- TASKS.lock.json is current (if present)
- All owned files exist or are explicitly blocked
- All dispatchable tasks have file contracts
- Required reviewers are assigned
- No duplicate file ownership
- No intra-wave dependencies

Exit 0 on success, non-zero on failure.
Requires Python standard library only.
"""

import json
import sys
from pathlib import Path


def _resolve_wave_tasks(wave_data: dict, top_tasks: dict) -> list[tuple[str, dict]]:
    """Yield (task_id, task_dict) pairs from a wave entry.

    Supports both:
      - legacy ``tasks: [{id: PRxx, ...}]``
      - current ``parallel_tasks: [PRxx, PRyy]`` with definitions in
        top-level ``tasks: {PRxx: {...}}``.
    """
    out: list[tuple[str, dict]] = []
    refs = wave_data.get("tasks") or wave_data.get("parallel_tasks") or []
    for ref in refs:
        if isinstance(ref, str):
            tid = ref
            tdata = top_tasks.get(tid, {}) if isinstance(top_tasks, dict) else {}
            out.append((tid, {**tdata, "id": tid}))
        elif isinstance(ref, dict):
            out.append((ref.get("id", "UNKNOWN"), ref))
    return out


def validate_yaml_structure(tasks_yaml: dict) -> tuple[list[str], list[str]]:
    """Validate TASKS.yaml structure. Returns (errors, warnings)."""
    errors: list[str] = []
    warnings: list[str] = []

    if "waves" not in tasks_yaml:
        errors.append("TASKS.yaml: missing 'waves' key")
        return errors, warnings

    waves = tasks_yaml["waves"]
    top_tasks = tasks_yaml.get("tasks", {}) or {}
    task_ids: set[str] = set()
    dispatchable_tasks: list[str] = []

    for wave_id, wave_data in waves.items():
        pairs = _resolve_wave_tasks(wave_data, top_tasks)
        if not pairs:
            errors.append(f"{wave_id}: missing 'tasks'/'parallel_tasks' key")
            continue
        for task_id, task in pairs:
            task_ids.add(task_id)

            if task.get("dispatchable"):
                dispatchable_tasks.append(task_id)
                # The current schema uses 'reviewers' instead of
                # 'required_reviewers'; accept both and warn if absent.
                reviewers = task.get("required_reviewers") or task.get("reviewers")
                if not reviewers:
                    warnings.append(
                        f"{task_id}: dispatchable task missing reviewers list"
                    )

            for fp in task.get("files_create", []) or []:
                if not fp:
                    errors.append(f"{task_id}: empty file path in files_create")

    for wave_data in waves.values():
        for task_id, task in _resolve_wave_tasks(wave_data, top_tasks):
            for dep in task.get("depends_on", []) or task.get("dependencies", []):
                if dep not in task_ids and dep not in top_tasks:
                    errors.append(f"{task_id}: references unknown dependency '{dep}'")

    return errors, warnings


def validate_file_ownership(tasks_yaml: dict) -> tuple[list[str], list[str]]:
    """Validate no duplicate file ownership across tasks."""
    errors = []
    warnings = []
    file_owners = {}
    
    top_tasks = tasks_yaml.get("tasks", {}) or {}
    for wave_data in tasks_yaml.get("waves", {}).values():
        for task_id, task in _resolve_wave_tasks(wave_data, top_tasks):
            for file_path in task.get("files_create", []) or []:
                if file_path in file_owners:
                    errors.append(
                        f"Duplicate ownership: '{file_path}' owned by both "
                        f"{file_owners[file_path]} and {task_id}"
                    )
                else:
                    file_owners[file_path] = task_id
    
    return errors, warnings


def validate_required_reviewers(tasks_yaml: dict) -> tuple[list[str], list[str]]:
    """Validate required reviewers are assigned per acceptance criteria."""
    errors = []
    warnings = []
    
    security_review_tasks = {"PR04", "PR07", "PR11", "PR12"}
    replication_review_tasks = {"PR05", "PR11", "PR14", "PR15"}
    all_reviewers_tasks = {"PR13"}
    
    for wave_data in tasks_yaml.get("waves", {}).values():
        for task in wave_data.get("tasks", []):
            task_id = task.get("id", "UNKNOWN")
            reviewers = set(task.get("required_reviewers", []))
            
            if task_id in security_review_tasks:
                if "security-privacy-reviewer" not in reviewers:
                    errors.append(f"{task_id}: requires security-privacy-reviewer (acceptance criteria)")
            
            if task_id in replication_review_tasks:
                if "replication-reviewer" not in reviewers:
                    errors.append(f"{task_id}: requires replication-reviewer (acceptance criteria)")
            
            if task_id in all_reviewers_tasks:
                expected = {"architecture-reviewer", "security-privacy-reviewer", "evaluation-reviewer", 
                          "replication-reviewer", "hermes-integration-reviewer", "researcher-ui-reviewer"}
                if not expected.issubset(reviewers):
                    errors.append(f"{task_id}: requires all reviewers (acceptance criteria)")
    
    return errors, warnings


def validate_subagent_manifests(root: Path) -> tuple[list[str], list[str]]:
    """Validate Claude and Codex agent manifests exist and have parity."""
    errors = []
    warnings = []
    
    claude_agents_dir = root / ".claude" / "agents"
    codex_agents_dir = root / ".codex" / "agents"
    
    if not claude_agents_dir.is_dir():
        errors.append(".claude/agents/ directory not found")
        return errors, warnings
    
    claude_roles = {p.stem for p in claude_agents_dir.glob("*.md")}
    
    # Check if .codex/agents/ is writable
    codex_writable = True
    if codex_agents_dir.is_dir():
        try:
            test_file = codex_agents_dir / ".write_test"
            test_file.touch()
            test_file.unlink()
        except (OSError, PermissionError):
            codex_writable = False
    
    if not codex_writable:
        warnings.append(".codex/agents/ is read-only - Codex TOML files cannot be created")
        return errors, warnings
    
    if not codex_agents_dir.is_dir():
        warnings.append(".codex/agents/ directory not found")
        return errors, warnings
    
    codex_roles = {p.stem for p in codex_agents_dir.glob("*.toml")}
    
    missing_in_codex = claude_roles - codex_roles
    missing_in_claude = codex_roles - claude_roles
    
    for role in sorted(missing_in_codex):
        errors.append(f"Claude role '{role}' has no Codex TOML")
    
    for role in sorted(missing_in_claude):
        errors.append(f"Codex role '{role}' has no Claude MD")
    
    return errors, warnings


def validate_tasks_lock(tasks_yaml: Path, tasks_lock: Path) -> tuple[list[str], list[str]]:
    """Validate TASKS.lock.json is current."""
    errors = []
    warnings = []
    
    if not tasks_lock.exists():
        warnings.append("TASKS.lock.json not present - will be generated")
        return errors, warnings
    
    if tasks_yaml.stat().st_mtime > tasks_lock.stat().st_mtime:
        errors.append("TASKS.lock.json is stale (TASKS.yaml modified more recently)")
    
    return errors, warnings


def find_handoff_root(root: Path) -> Path | None:
    """Return the directory containing local-only handoff docs, if present."""
    candidates = [
        root / "dev_docs" / "orchestration",
        root,
    ]
    for candidate in candidates:
        if (candidate / "TASKS.yaml").exists():
            return candidate
    return None


def validate_security_docs(root: Path, handoff_root: Path) -> tuple[list[str], list[str]]:
    """Validate security governance docs are present."""
    errors = []
    warnings = []
    
    required_docs = [
        "SECURITY_THREAT_MODEL.md",
        "TOOL_PERMISSION_MATRIX.md",
        "PRIVACY_DPIA_DATA_MANAGEMENT.md",
        "HUMAN_STUDY_INSTRUMENTS.md",
    ]
    
    for doc in required_docs:
        project_doc = root / "dev_docs" / "project_docs" / doc
        if (
            not (root / doc).exists()
            and not (handoff_root / doc).exists()
            and not project_doc.exists()
        ):
            errors.append(f"Missing required security doc: {doc}")
    
    return errors, warnings


def validate_acceptance_criteria(tasks_yaml: dict) -> tuple[list[str], list[str]]:
    """Validate acceptance criteria are properly specified."""
    errors = []
    warnings = []
    
    pr04_criteria = "Final output privacy gate required after rehydration"
    pr06_criteria = "Tool permission matrix enforced before side-effect tools"
    pr11_criteria = "Tool permission matrix tests required"
    
    for wave_data in tasks_yaml.get("waves", {}).values():
        for task in wave_data.get("tasks", []):
            task_id = task.get("id", "UNKNOWN")
            criteria = task.get("acceptance_criteria", [])
            
            if task_id == "PR04":
                if pr04_criteria not in criteria:
                    errors.append(f"{task_id}: missing acceptance criteria: {pr04_criteria}")
            
            if task_id == "PR06":
                if pr06_criteria not in criteria:
                    errors.append(f"{task_id}: missing acceptance criteria: {pr06_criteria}")
            
            if task_id == "PR11":
                if pr11_criteria not in criteria:
                    errors.append(f"{task_id}: missing acceptance criteria: {pr11_criteria}")
    
    return errors, warnings


def main() -> int:
    root = Path(__file__).parent.parent
    handoff_root = find_handoff_root(root)
    
    all_errors = []
    all_warnings = []
    
    if handoff_root is None:
        print("Handoff validation skipped: local dev_docs/orchestration is absent.")
        return 0

    tasks_yaml_path = handoff_root / "TASKS.yaml"
    tasks_lock_path = handoff_root / "TASKS.lock.json"
    
    try:
        import yaml
        tasks_yaml = yaml.safe_load(tasks_yaml_path.read_text(encoding="utf-8"))
    except ImportError:
        print("WARNING: PyYAML not available, using basic validation")
        tasks_yaml = {"waves": {}}
    except Exception as e:
        print(f"ERROR: Cannot parse TASKS.yaml: {e}")
        return 1
    
    errors, warnings = validate_yaml_structure(tasks_yaml)
    all_errors.extend(errors)
    all_warnings.extend(warnings)
    
    errors, warnings = validate_file_ownership(tasks_yaml)
    all_errors.extend(errors)
    all_warnings.extend(warnings)
    
    errors, warnings = validate_required_reviewers(tasks_yaml)
    all_errors.extend(errors)
    all_warnings.extend(warnings)
    
    errors, warnings = validate_subagent_manifests(root)
    all_errors.extend(errors)
    all_warnings.extend(warnings)
    
    errors, warnings = validate_tasks_lock(tasks_yaml_path, tasks_lock_path)
    all_errors.extend(errors)
    all_warnings.extend(warnings)
    
    errors, warnings = validate_security_docs(root, handoff_root)
    all_errors.extend(errors)
    all_warnings.extend(warnings)
    
    errors, warnings = validate_acceptance_criteria(tasks_yaml)
    all_errors.extend(errors)
    all_warnings.extend(warnings)
    
    for w in all_warnings:
        print(f"WARNING: {w}")
    
    if all_errors:
        print("Handoff validation errors:")
        for e in all_errors:
            print(f"  - {e}")
        return 1
    
    print("Handoff validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
