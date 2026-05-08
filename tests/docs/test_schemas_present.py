"""Schemas required by PR19B / PR20F / PR22B-D."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
REQUIRED = [
    "agent_diary_entry",
    "continuity_exposure_event",
    "external_memory_candidate",
    "feedback_propagation_trace",
    "memory_dynamics_event",
    "memory_exposure_event",
    "prompt_context_pack",
    "researcher_feedback_event",
    "roleplay_admission_event",
    "ui_review_status",
]


@pytest.mark.parametrize("name", REQUIRED)
def test_schema_present_and_parseable(name: str) -> None:
    p = ROOT / "schemas" / f"{name}.schema.json"
    assert p.exists(), f"missing schemas/{name}.schema.json"
    json.loads(p.read_text())  # raises on bad JSON
