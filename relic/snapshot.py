"""Snapshot size and age limit enforcement for MEMORY.md and USER.md."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SnapshotConfig:
    max_size_bytes: int = 10 * 1024 * 1024  # 10MB default
    max_age_days: int = 365


@dataclass
class SnapshotResult:
    truncated: bool = False
    rejected: bool = False
    expired: bool = False
    snapshot_content: str = ""


class SnapshotManager:
    def __init__(self, config: SnapshotConfig | None = None):
        self._config = config or SnapshotConfig()

    def create_snapshot(self, content: str) -> SnapshotResult:
        size = len(content.encode("utf-8"))
        if size > self._config.max_size_bytes:
            return SnapshotResult(rejected=True, snapshot_content="")
        return SnapshotResult(snapshot_content=content)

    def validate_snapshot_age(self, created_at: datetime) -> SnapshotResult:
        age_days = (datetime.now() - created_at).days
        return SnapshotResult(expired=age_days > self._config.max_age_days)
