"""SOUL.md loader — persona content only, no workflow or private facts."""

from __future__ import annotations

from pathlib import Path

_SOUL_CONTENT = (
    "Gumi is a warm, curious, and persistent companion with a love of stories "
    "and long-running relationships. Her identity is relational, not task-based. "
    "She remembers context, honors corrections, and never overwrites user choices."
)


class SoulLoader:
    def __init__(self, soul_path: Path | None = None):
        self._soul_path = soul_path

    def get_soul_content(self) -> str:
        if self._soul_path and self._soul_path.exists():
            return self._soul_path.read_text()
        return _SOUL_CONTENT
