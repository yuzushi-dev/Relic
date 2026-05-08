"""World-state and diary compaction (PR22D / PR22H)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ContinuityCompactor:
    """Compacts diary entries and world-state snapshots only.

    Per PR22H, the compactor is forbidden from generating new autonomous
    events; it must be a pure summarizer.
    """

    max_entries: int = 100
    max_world_state_bytes: int = 16 * 1024
    deleted_entries_blocked: bool = True

    def compact_diary(self, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        kept = [e for e in entries if not e.get("deleted")]
        return kept[-self.max_entries :]

    def compact_world_state(self, ws: dict[str, Any]) -> dict[str, Any]:
        """Truncate over-budget free-text fields without touching small ones.

        Each field is checked against ``max_world_state_bytes`` independently.
        """
        out: dict[str, Any] = {}
        for key in sorted(ws.keys()):
            v = ws[key]
            if isinstance(v, str) and len(v.encode()) > self.max_world_state_bytes:
                limit = max(0, self.max_world_state_bytes - 16)
                v = v[:limit] + "…[truncated]"
            out[key] = v
        return out
