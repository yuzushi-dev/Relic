"""ExternalMemoryCandidate model (PR19B).

External memory providers emit *candidates*, never relational truth. Relic
treats every candidate as untrusted input until the admission policy and
correction layer have signed off.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class ExternalMemoryCandidate:
    candidate_id: str
    provider: str
    subject_id: str
    text: str
    score: float
    redacted: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
