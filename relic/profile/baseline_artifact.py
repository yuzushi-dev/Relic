"""Build and write subject baseline artifacts."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "v1.0"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_baseline_artifact(state: dict[str, Any]) -> dict[str, Any]:
    """Build a schema-shaped baseline artifact from bootstrap state."""
    return {
        "schema_version": SCHEMA_VERSION,
        "bootstrap_session_id": state["bootstrap_session_id"],
        "researcher_id": state["researcher_id"],
        "subject_id": state["subject_id"],
        "creation_date": state.get("creation_date") or _now_iso(),
        "baseline_method": state["baseline_method"],
        "baseline_version": 1,
        "self_report_fields": state["self_report_fields"],
        "researcher_coded_fields": state["researcher_coded_fields"],
        "system_inferred_fields": {
            "estimated_engagement_level": {"value": None, "origin": "system-inferred"},
            "inferred_relational_style": {"value": None, "origin": "system-inferred"},
            "session_affect_summary": {"value": None, "origin": "system-inferred"},
            "response_latency_pattern": {"value": None, "origin": "system-inferred"},
        },
        "interaction_preferences": state["interaction_preferences"],
        "relational_expectations": state["relational_expectations"],
        "boundaries": state["boundaries"],
        "opt_out_categories": state["opt_out_categories"],
        "risk_flags": state["risk_flags"],
        "item_battery": state.get("item_battery"),
        "version_history": [
            {
                "version": 1,
                "edited_at": state.get("creation_date") or _now_iso(),
                "edited_by": state["researcher_id"],
                "fields_changed": ["initial bootstrap creation"],
                "edit_mode": "manual",
                "change_summary": "initial bootstrap creation",
            }
        ],
    }


def write_baseline_artifact(profile_dir: str | Path, artifact: dict[str, Any]) -> Path:
    """Write baseline_user_profile.json with stable formatting."""
    path = Path(profile_dir) / "baseline_user_profile.json"
    path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
