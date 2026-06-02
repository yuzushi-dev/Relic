"""PR22F, neutral content is allowed."""
from __future__ import annotations

from relic.gumi_plugin import OutputCritic


def test_allows_neutral() -> None:
    v = OutputCritic().review("Let's continue our story tomorrow.")
    assert v.allow is True
