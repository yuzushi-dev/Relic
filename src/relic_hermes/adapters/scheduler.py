"""Hermes scheduler binding."""

from __future__ import annotations

from pathlib import Path


class HermesCronBinding:
    """Expose the Hermes cron state location as an explicit adapter seam."""

    def __init__(self, hermes_home: str | Path) -> None:
        self.hermes_home = Path(hermes_home)

    def jobs_location(self) -> Path:
        return self.hermes_home / "cron" / "jobs.json"

