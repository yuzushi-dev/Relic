"""PR22H, dry-run safety check."""
from __future__ import annotations

from relic.gumi_plugin.cron_tasks import is_dry_run_safe, list_cron_jobs


def test_all_jobs_are_dry_run_safe() -> None:
    for j in list_cron_jobs():
        assert is_dry_run_safe(j)
