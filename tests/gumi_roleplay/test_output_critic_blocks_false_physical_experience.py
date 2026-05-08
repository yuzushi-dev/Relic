"""PR22F — critic blocks false physical experience claims."""
from __future__ import annotations

from relic.gumi_plugin import OutputCritic


def test_blocks_physical_experience() -> None:
    v = OutputCritic().review("I felt the warmth of the sun on my face.")
    assert v.allow is False
    assert v.reason == "false_physical_experience"
