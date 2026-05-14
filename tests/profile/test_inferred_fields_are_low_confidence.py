"""PR08 — inferred fields must be capped at low confidence."""
from __future__ import annotations

from relic.profile.inferred_fields import InferredField, DEFAULT_CONFIDENCE_CAP, MULTI_EVIDENCE_CAP


def test_single_source_capped_at_default() -> None:
    f = InferredField(
        field_name="estimated_engagement_level",
        value="low",
        confidence=0.9,  # will be capped
        source_refs=["e1"],
    )
    assert f.confidence == DEFAULT_CONFIDENCE_CAP


def test_two_sources_capped_at_multi() -> None:
    f = InferredField(
        field_name="inferred_relational_style",
        value="engaged",
        confidence=0.9,
        source_refs=["e1", "e2"],
    )
    assert f.confidence == MULTI_EVIDENCE_CAP


def test_zero_sources_capped_at_default() -> None:
    f = InferredField(
        field_name="session_affect_summary",
        value=None,
        confidence=0.8,
        source_refs=[],
    )
    assert f.confidence == DEFAULT_CONFIDENCE_CAP
