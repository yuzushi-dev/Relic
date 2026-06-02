"""PR19C, built-in-only condition: no external provider invoked."""
from __future__ import annotations

from relic.gumi_memory.providers.holographic import HolographicCondition


def test_holographic_is_evaluation_only() -> None:
    c = HolographicCondition()
    assert c.runtime_provider is False
    assert c.integration_class == "evaluation-only"
