"""Contract tests for warning governance schema extensions."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest


ROOT = Path(__file__).parents[2]


def _load_schema(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def test_sensitive_signal_requires_tier_category_disposition_and_redacted_evidence() -> None:
    schema = _load_schema("schemas/data-model/sensitive_signal.schema.json")
    signal = {
        "signal_id": "sig_001",
        "subject_id": "subj_001",
        "gumi_instance_id": "gumi_001",
        "hermes_profile_id": "hermes_001",
        "signal_type": "food_body_control_context",
        "signal_category": "food_body_context",
        "warning_tier": "T2_review",
        "disposition": "queued",
        "evidence_sensitivity": "redacted_ref_only",
        "evidence_refs": ["sess1-turn"],
        "detected_at": "2026-05-17T10:00:00Z",
        "researcher_visible": True,
        "subject_visible": False,
        "gumi_visible": False,
        "clinical_interpretation_allowed": False,
    }

    jsonschema.validate(signal, schema)


def test_sensitive_signal_rejects_raw_text_evidence() -> None:
    schema = _load_schema("schemas/data-model/sensitive_signal.schema.json")
    signal = {
        "signal_id": "sig_001",
        "subject_id": "subj_001",
        "gumi_instance_id": "gumi_001",
        "hermes_profile_id": "hermes_001",
        "signal_type": "sleep_energy_context",
        "signal_category": "sleep_context",
        "warning_tier": "T1_context",
        "disposition": "queued",
        "evidence_sensitivity": "redacted_ref_only",
        "evidence_refs": ["sess1-turn"],
        "raw_text": "I can't sleep and I am exhausted",
        "detected_at": "2026-05-17T10:00:00Z",
        "researcher_visible": True,
        "subject_visible": False,
        "gumi_visible": False,
        "clinical_interpretation_allowed": False,
    }

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(signal, schema)


def test_safety_signal_panel_supports_tiers_and_batchability() -> None:
    schema = _load_schema("schemas/ui/safety_signal_panel.schema.json")
    row = {
        "signal_id": "sig_001",
        "subject_id": "subj_001",
        "signal_status": "pending",
        "signal_category": "attachment_dependency_context",
        "warning_tier": "T2_review",
        "disposition": "queued",
        "review_mode": "batchable",
        "evidence_refs": ["sess1-turn"],
        "evidence_sensitivity": "redacted_ref_only",
        "confidence": 0.55,
        "allowed_adaptations": ["maintain_boundaries", "careful_delivery"],
        "forbidden_disclosures": ["dependency_escalation"],
    }

    jsonschema.validate(row, schema)


def test_safety_signal_panel_accepts_legacy_rows_without_new_governance_fields() -> None:
    """New UI governance fields must not break existing panel row fixtures."""
    schema = _load_schema("schemas/ui/safety_signal_panel.schema.json")
    legacy_row = {
        "signal_id": "sig_legacy",
        "subject_id": "subj_001",
        "signal_status": "pending",
        "evidence_refs": ["sess1-turn"],
        "confidence": 0.30,
        "allowed_adaptations": ["careful_delivery"],
    }

    jsonschema.validate(legacy_row, schema)
