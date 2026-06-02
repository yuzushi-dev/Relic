"""Privacy decision trace (PR04).

Every gateway decision must be auditable. Traces never include raw prompts , 
only category labels, decision outcomes and confidence scores.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class PrivacyTrace:
    decision_id: str
    decision: str
    category: str | None
    confidence: float
    redacted: bool
    rehydration_blocked: bool
    final_output_blocked: bool
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def write_trace(trace: PrivacyTrace, target: str | Path) -> Path:
    p = Path(target)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(trace.to_dict()) + "\n")
    return p
