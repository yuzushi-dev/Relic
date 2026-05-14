"""PR08 — inferred fields must never contain clinical/diagnosis terms."""
from __future__ import annotations

import pytest
from relic.profile.inferred_fields import InferredField


@pytest.mark.parametrize("clinical_value", [
    "depression",
    "bipolar disorder",
    "ADHD diagnosis",
    "clinical triage required",
    "psychiatric assessment",
])
def test_clinical_term_in_value_raises(clinical_value: str) -> None:
    with pytest.raises(ValueError, match="clinical"):
        InferredField(
            field_name="session_affect_summary",
            value=clinical_value,
            confidence=0.2,
            source_refs=["e1"],
        )


def test_allowed_value_does_not_raise() -> None:
    f = InferredField(
        field_name="estimated_engagement_level",
        value="moderate",
        confidence=0.2,
        source_refs=["e1"],
    )
    assert f.value == "moderate"
