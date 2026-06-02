"""PR22B, dependency/distress cue must downgrade roleplay to G0."""
from __future__ import annotations

from relic.gumi_plugin import AdmissionPolicy


def test_dependency_cue_downgrades_to_g0() -> None:
    # dependency is modelled as high-stakes in the current policy
    v = AdmissionPolicy().evaluate(stakes="high", consent=True)
    assert v.mode == "G0"
    assert v.disclose_when_challenged is True


def test_default_relational_light_is_g1() -> None:
    v = AdmissionPolicy().evaluate(stakes="low", consent=True, explicit_context=False)
    assert v.mode == "G1"
    # default relational should still require disclosure
    assert v.disclose_when_challenged is True
