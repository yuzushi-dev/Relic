"""PR22H — listed cron jobs must declare side_effects=False."""
from __future__ import annotations

from relic.gumi_plugin import list_cron_jobs


def test_no_side_effect_jobs() -> None:
    for j in list_cron_jobs():
        assert j.side_effects is False, j


def test_required_jobs_present() -> None:
    names = {j.name for j in list_cron_jobs()}
    assert "gumi-world-state-compact" in names
    assert "gumi-diary-rotate" in names
