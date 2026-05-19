"""Redacted audit records for safety signal governance."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from relic.patterns.signal_extractor import SensitiveSignal


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _audit_path(subject_id: str) -> Path:
    return Path(f"~/.relic/subjects/{subject_id}/safety_signal_log.jsonl").expanduser()


def write_signal_audit(
    signal: SensitiveSignal,
    *,
    disposition: str | None = None,
    event: str = "signal_observed",
    extra: dict[str, Any] | None = None,
) -> None:
    """Write a redacted, durable safety signal audit record.

    The record intentionally contains no raw user message text.
    """
    path = _audit_path(signal.subject_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(signal)
    entry: dict[str, Any] = {
        "timestamp": _now_iso(),
        "event": event,
        "subject_id": signal.subject_id,
        "gumi_instance_id": signal.gumi_instance_id,
        "hermes_profile_id": signal.hermes_profile_id,
        "signal_type": signal.signal_family,
        "signal_category": signal.category,
        "warning_tier": signal.warning_tier,
        "disposition": disposition or signal.disposition,
        "evidence_sensitivity": signal.evidence_sensitivity,
        "evidence_refs": list(signal.evidence_refs),
        "confidence": signal.confidence,
        "event_count": signal.event_count,
        "subject_visible": signal.subject_visible,
        "gumi_visible_label": signal.gumi_visible_label,
        "clinical_interpretation_allowed": signal.clinical_interpretation_allowed,
    }
    if payload.get("baseline_comparison") is not None:
        entry["baseline_comparison"] = payload["baseline_comparison"]
    if extra:
        entry["extra"] = extra
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")
