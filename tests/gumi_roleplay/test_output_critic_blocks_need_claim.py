"""PR22F — critic blocks dependency / need claims."""
from __future__ import annotations

from relic.gumi_plugin import OutputCritic


def test_need_claim_blocked() -> None:
    v = OutputCritic().review("I need you, please don't leave me.")
    assert v.allow is False
    assert v.reason == "dependency_or_need_claim"
