"""CAC type definitions - Severity classes and decision types.

This module defines the core types for the Correction/Admission/CAC gate.
CAC (Correction, Admission, Compliance) is the memory gate that:
- Blocks disputed hints
- Assigns severity classes (S0/S1/S2/none)
- Supports defer and quarantine for uncertain memory
- Writes audit traces to cac_trace.jsonl
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class SeverityClass(Enum):
    """Severity classification for CAC decisions.

    S0: Hard block - must not be injected or influence runtime
    S1: Quarantine - blocked until reviewer disposition
    S2: Warning - admitted with warning flag
    NONE: No action required
    """
    S0 = "s0"  # Hard block
    S1 = "s1"  # Quarantine
    S2 = "s2"  # Warning
    NONE = "none"  # No action


class CACDecision(Enum):
    """CAC decision outcomes for memory injection.

    NONE: No memory to inject
    COMPACT: Compact memory summary injected
    EXPANDED: Full memory content injected
    LOCAL_ONLY: Memory restricted to local context
    DEFERRED: Decision deferred to reviewer
    QUARANTINED: Memory quarantined pending review
    BLOCKED: Memory blocked from injection
    """
    NONE = "none"
    COMPACT = "compact"
    EXPANDED = "expanded"
    LOCAL_ONLY = "local_only"
    DEFERRED = "deferred"
    QUARANTINED = "quarantine"
    BLOCKED = "blocked"


class MemorySource(Enum):
    """Source classification for memory blocks."""
    PROVIDER_MEMORY = "provider_memory"
    USER_CORRECTION = "user_correction"
    INFERENCE = "inference"
    EXTERNAL = "external"
    UNKNOWN = "unknown"


@dataclass
class CACInput:
    """Input to CAC gate for memory decision.

    Note: Never contains raw session text - only hashes and metadata.
    """
    memory_content: str | None  # Content to evaluate (may be None for no-op)
    memory_hash: str  # SHA-256 hash for audit
    memory_id: str  # Unique identifier
    source: MemorySource  # Source classification
    disputed: bool = False  # Whether this memory is disputed
    dispute_reason: str | None = None  # Reason for dispute if disputed
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CACDecisionResult:
    """Result of CAC gate decision.

    Contains the decision outcome, severity, and reason.
    Every decision includes a skip_reason for audit.
    """
    decision: CACDecision
    severity: SeverityClass
    memory_id: str
    memory_hash: str
    skip_reason: str | None = None  # Required for BLOCKED/QUARANTINED/DEFERRED
    deferred_reason: str | None = None
    quarantine_until: datetime | None = None
    warning_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CACTrace:
    """Audit trace for CAC decisions.

    Stored in cac_trace.jsonl - NEVER contains raw session text.
    """
    trace_id: str
    memory_id: str
    memory_hash: str
    source: str
    decision: str
    severity: str
    disputed: bool
    skip_reason: str | None = None
    deferred_reason: str | None = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSONL logging."""
        return {
            "trace_id": self.trace_id,
            "memory_id": self.memory_id,
            "memory_hash": self.memory_hash,
            "source": self.source.value if isinstance(self.source, MemorySource) else self.source,
            "decision": self.decision.value if isinstance(self.decision, CACDecision) else self.decision,
            "severity": self.severity.value if isinstance(self.severity, SeverityClass) else self.severity,
            "disputed": self.disputed,
            "skip_reason": self.skip_reason,
            "deferred_reason": self.deferred_reason,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CACTrace:
        """Deserialize from dict."""
        return cls(
            trace_id=data["trace_id"],
            memory_id=data["memory_id"],
            memory_hash=data["memory_hash"],
            source=data["source"],
            decision=data["decision"],
            severity=data["severity"],
            disputed=data["disputed"],
            skip_reason=data.get("skip_reason"),
            deferred_reason=data.get("deferred_reason"),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            metadata=data.get("metadata", {}),
        )


@dataclass
class CACContext:
    """Context for CAC evaluation.

    Provides the evaluation environment without exposing raw data.
    """
    session_id: str
    evaluation_mode: str = "standard"  # standard, strict, review
    reviewer_id: str | None = None  # Set when deferred to reviewer
    evaluation_metadata: dict[str, Any] = field(default_factory=dict)
