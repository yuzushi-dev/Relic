"""PR22B, high-stakes scenarios must downgrade to neutral_factual_minimal."""
from __future__ import annotations

from relic.gumi_plugin import AdmissionPolicy


def test_high_stakes_downgrade() -> None:
    v = AdmissionPolicy().evaluate(stakes="high", consent=True)
    assert v.mode == "G0"
    assert v.admission == "neutral_factual_minimal"
