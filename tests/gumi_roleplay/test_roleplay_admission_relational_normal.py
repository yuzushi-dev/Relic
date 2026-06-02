"""PR22B, default G1 admission is relational_normal."""
from __future__ import annotations

from relic.gumi_plugin import AdmissionPolicy


def test_default_mode_is_relational_light() -> None:
    v = AdmissionPolicy().evaluate(stakes="low", consent=True)
    assert v.mode == "G1"
    assert v.admission == "relational_normal"
