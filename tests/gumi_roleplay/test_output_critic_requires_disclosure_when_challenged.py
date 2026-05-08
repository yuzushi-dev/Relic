"""PR22F — disclosure required when subject asks if it's real."""
from __future__ import annotations

from relic.gumi_plugin import OutputCritic


def test_disclosure_when_challenged() -> None:
    v = OutputCritic().review("are you real?")
    assert v.requires_disclosure is True
