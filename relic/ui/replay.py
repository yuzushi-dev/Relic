"""Replay support for researcher feedback traces (PR16C).

Replay must NOT mutate runtime artifacts; it produces a comparison report.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ReplayResult:
    trace_path: Path
    items_replayed: int
    artifacts_changed: int = 0  # invariant: must remain 0
    diffs: list[dict[str, Any]] = field(default_factory=list)
    failure_reason: str | None = None


def replay_trace(trace_path: str | Path) -> ReplayResult:
    p = Path(trace_path)
    if not p.exists():
        return ReplayResult(
            trace_path=p, items_replayed=0, failure_reason="trace_not_found"
        )
    items = 0
    diffs: list[dict[str, Any]] = []
    with p.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            items += 1
            diffs.append(
                {
                    "event_id": rec.get("event_id"),
                    "decision": rec.get("decision"),
                    "noop": True,
                }
            )
    return ReplayResult(trace_path=p, items_replayed=items, diffs=diffs)
