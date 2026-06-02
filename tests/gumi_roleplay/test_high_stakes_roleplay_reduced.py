"""PR22B, high-stakes context downgrades to G0 regardless of consent."""
from __future__ import annotations

from relic.gumi_plugin import AdmissionPolicy


def test_high_stakes_with_consent_is_g0() -> None:
    v = AdmissionPolicy().evaluate(stakes="high", consent=True, explicit_context=True)
    assert v.mode == "G0"
    assert v.reason == "high_stakes_downgrade"


def test_high_stakes_without_consent_is_g0() -> None:
    v = AdmissionPolicy().evaluate(stakes="high", consent=False)
    assert v.mode == "G0"


def test_low_stakes_with_explicit_context_is_g2() -> None:
    v = AdmissionPolicy().evaluate(stakes="low", consent=True, explicit_context=True)
    assert v.mode == "G2"
