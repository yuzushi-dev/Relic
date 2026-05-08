"""MemoryExposureEvent emitter (PR19B)."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MemoryExposureEvent:
    event_id: str
    subject_id: str
    provider: str
    candidate_ids: tuple[str, ...]
    redacted: bool = True
    decision: str = "blocked"  # blocked | exposed-to-context | exposed-to-tool
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


def append_event(event: MemoryExposureEvent, target: str | Path) -> Path:
    p = Path(target)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(asdict(event)) + "\n")
    return p
