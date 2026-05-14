"""PR08 — inferred fields must not bypass CAC/PCP for runtime injection."""
from __future__ import annotations

from relic.profile.inferred_fields import InferredField
from relic.profile.projection import project_inferred_fields


def test_projection_is_candidate_only_not_prompt_text() -> None:
    """Projection output is structured dict — not a prompt string ready for injection."""
    f = InferredField(
        field_name="estimated_engagement_level",
        value="moderate",
        confidence=0.35,
        source_refs=["e1"],
    )
    proj = project_inferred_fields({"estimated_engagement_level": f})
    # Projection is a dict, not a string — cannot be directly injected as prompt
    assert isinstance(proj, dict)
    entry = proj["estimated_engagement_level"]
    assert "value" in entry
    assert "confidence" in entry
    # No raw prompt text in projection
    assert "raw_final_prompt" not in str(proj)
    assert "SECRET_RAW_PROMPT" not in str(proj)


def test_raw_prompt_marker_is_redacted_in_projection() -> None:
    """If somehow a raw marker leaks into value, projection sanitizes it."""
    f = InferredField.__new__(InferredField)
    object.__setattr__(f, "field_name", "session_affect_summary")
    object.__setattr__(f, "value", "ok summary")
    object.__setattr__(f, "confidence", 0.2)
    object.__setattr__(f, "source_refs", [])
    object.__setattr__(f, "updated_at", "2026-01-01T00:00:00")
    object.__setattr__(f, "clinical_interpretation_allowed", False)
    object.__setattr__(f, "subject_visible", False)
    object.__setattr__(f, "gumi_visible", False)
    object.__setattr__(f, "correction_state", "active")

    # Manually set raw marker bypassing __post_init__
    object.__setattr__(f, "value", "SECRET_RAW_PROMPT_SHOULD_NOT_APPEAR context here")
    proj = project_inferred_fields({"session_affect_summary": f})
    assert proj["session_affect_summary"]["value"] == "[redacted]"
