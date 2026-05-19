"""Warning governance metadata must not enter Hermes memory context."""

from __future__ import annotations


def test_warning_governance_marker_is_not_prefetched_to_hermes_memory() -> None:
    from relic.hermes_plugin.memory_provider import RelicMemoryProvider

    provider = RelicMemoryProvider(subject_id="s1")
    marker = {
        "origin": "sensitive_signal",
        "subject_confirmation": True,
        "subject_words": ["dependency_escalation", "T2_review"],
        "warning_tier": "T2_review",
    }

    assert provider._is_safe_to_surface(marker) is False
