"""Cron schedule contract (PR22H)."""
from __future__ import annotations

import re
from dataclasses import dataclass

_FIELD = r"(\*|\d+(?:-\d+)?(?:/\d+)?(?:,\d+(?:-\d+)?(?:/\d+)?)*)"
CRON_RE = re.compile(rf"^{_FIELD}\s+{_FIELD}\s+{_FIELD}\s+{_FIELD}\s+{_FIELD}$")


@dataclass(frozen=True)
class ScheduleConfig:
    job_name: str
    cron: str
    timezone: str = "UTC"

    def validate(self) -> bool:
        return bool(CRON_RE.match(self.cron))
