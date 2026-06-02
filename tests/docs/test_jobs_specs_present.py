"""PR10, jobs/nightly.yaml and jobs/weekly.yaml must exist."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_nightly_present() -> None:
    assert (ROOT / "jobs" / "nightly.yaml").exists()


def test_weekly_present() -> None:
    assert (ROOT / "jobs" / "weekly.yaml").exists()
