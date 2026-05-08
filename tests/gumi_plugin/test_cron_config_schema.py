"""PR22H — cron schedule contract."""
from __future__ import annotations

from relic.gumi_plugin.cron_schedule import ScheduleConfig


def test_valid_cron_passes() -> None:
    s = ScheduleConfig(job_name="x", cron="0 3 * * *")
    assert s.validate() is True


def test_invalid_cron_fails() -> None:
    assert ScheduleConfig(job_name="x", cron="not a cron").validate() is False
