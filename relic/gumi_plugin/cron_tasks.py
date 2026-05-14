"""Cron continuity maintenance tasks (PR22H)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CronJob:
    name: str
    schedule: str
    description: str
    side_effects: bool = False  # must remain False for compaction-only jobs


_JOBS: tuple[CronJob, ...] = (
    CronJob(
        name="gumi-world-state-compact",
        schedule="0 3 * * *",
        description="Nightly world-state compaction (no autonomous events)",
        side_effects=False,
    ),
)


def list_cron_jobs() -> tuple[CronJob, ...]:
    return _JOBS


def is_dry_run_safe(job: CronJob) -> bool:
    return not job.side_effects
