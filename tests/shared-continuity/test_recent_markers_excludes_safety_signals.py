"""recent_markers must not surface researcher-only/safety markers to Gumi."""

from __future__ import annotations

from relic.shared_continuity.service import ContinuityService


def test_recent_markers_excludes_hindsight_safety_signal() -> None:
    service = ContinuityService()
    service.remember(
        subject_id="s1",
        gumi_instance_id="g1",
        hermes_profile_id="h1",
        subject_words=["dependency_escalation"],
        source_type="hindsight_safety_signal",
    )

    assert service.recent_markers("s1", "g1", "h1") == []


def test_recent_markers_excludes_researcher_only_note() -> None:
    service = ContinuityService()
    service.remember(
        subject_id="s1",
        gumi_instance_id="g1",
        hermes_profile_id="h1",
        subject_words=["researcher-only warning"],
        source_type="researcher_only_note",
    )

    assert service.recent_markers("s1", "g1", "h1") == []
