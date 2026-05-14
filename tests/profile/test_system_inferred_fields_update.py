"""PR08 — system_inferred_fields update from governed traces."""
from __future__ import annotations

import pytest
from relic.profile.system_inference import SystemInferenceUpdater


def test_engagement_level_updates_from_exposure_events() -> None:
    updater = SystemInferenceUpdater()
    events = [
        {"event_id": "e1", "redacted_summary": "turn 1"},
        {"event_id": "e2", "redacted_summary": "turn 2"},
        {"event_id": "e3", "redacted_summary": "turn 3"},
    ]
    field = updater.update_engagement_level(events)
    assert field.value == "moderate"
    assert field.confidence > 0
    assert field.clinical_interpretation_allowed is False


def test_relational_style_updates_from_dynamics_events() -> None:
    updater = SystemInferenceUpdater()
    events = [
        {"event_id": "d1", "event_type": "reinforcement"},
        {"event_id": "d2", "event_type": "reinforcement"},
        {"event_id": "d3", "event_type": "decay"},
    ]
    field = updater.update_relational_style(events)
    assert field.value == "engaged"


def test_run_returns_all_four_fields() -> None:
    updater = SystemInferenceUpdater()
    result = updater.run(subject_id="subj-1")
    assert "estimated_engagement_level" in result
    assert "inferred_relational_style" in result
    assert "session_affect_summary" in result
    assert "response_latency_pattern" in result


def test_response_latency_pattern_fast() -> None:
    updater = SystemInferenceUpdater()
    meta = [{"source_ref": "m1", "response_latency_ms": 500}]
    field = updater.update_response_latency_pattern(meta)
    assert field.value == "fast"
