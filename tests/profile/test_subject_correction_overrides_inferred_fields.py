"""PR08 — subject correction must override inferred field value."""
from __future__ import annotations

from relic.profile.inferred_fields import InferredField


def test_apply_correction_sets_corrected_state() -> None:
    f = InferredField(
        field_name="inferred_relational_style",
        value="engaged",
        confidence=0.35,
        source_refs=["d1"],
    )
    corrected = f.apply_correction()
    assert corrected.correction_state == "corrected"
    assert corrected.value is None
    assert corrected.confidence == 0.0


def test_corrected_field_cannot_be_used_as_active() -> None:
    f = InferredField(
        field_name="estimated_engagement_level",
        value="high",
        confidence=0.3,
        source_refs=["e1"],
    )
    corrected = f.apply_correction()
    # correction_state blocks use in update loop
    assert corrected.correction_state != "active"
