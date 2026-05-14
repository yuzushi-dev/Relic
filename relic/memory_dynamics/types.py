"""Type definitions for memory dynamics.

This module provides type definitions for the memory dynamics system including:
- Decay, reinforcement, association mechanisms
- Consolidation and projection operations
- Mechanism reports and traces
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class MemoryMechanism(str, Enum):
    """Types of memory dynamics mechanisms."""
    DECAY = "decay"
    REINFORCEMENT = "reinforcement"
    ASSOCIATION = "association"
    CONSOLIDATION = "consolidation"
    MEMORY_EVOLUTION = "memory_evolution"
    CONFLICT_TRACKING = "conflict_tracking"


class SourceCandidate(str, Enum):
    """Source candidates for memory storage."""
    DORY = "dory"
    MEM7 = "mem7"
    A_MEM = "a_mem"
    HIPPO = "hippo"
    INTERNAL = "internal"


class DecisionOutcome(str, Enum):
    """Outcome decisions for memory dynamics."""
    ALLOW = "allow"
    BLOCK = "block"
    DOWNGRADE = "downgrade"
    NEEDS_REVIEW = "needs_review"


class SalienceLevel(str, Enum):
    """Memory salience levels."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    MINIMAL = "minimal"


class CorrectionStatus(str, Enum):
    """Correction status for memory blocks."""
    ACTIVE = "active"
    RESOLVED = "resolved"
    PENDING = "pending"
    NONE = "none"


@dataclass
class SalienceResult:
    """Result of salience calculation."""
    salience_score: float
    salience_level: SalienceLevel
    correction_respected: bool = True
    correction_active: bool = False
    privacy_level: str = "SAFE"
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "salience_score": self.salience_score,
            "salience_level": self.salience_level.value,
            "correction_respected": self.correction_respected,
            "correction_active": self.correction_active,
            "privacy_level": self.privacy_level,
        }


@dataclass
class SpreadingActivationResult:
    """Result of spreading activation check."""
    allowed: bool
    blocked_by: str | None = None
    activation_propagated: bool = False
    correction_respected: bool = False
    activated_content_corrected: bool = False
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "blocked_by": self.blocked_by,
            "activation_propagated": self.activation_propagated,
            "correction_respected": self.correction_respected,
            "activated_content_corrected": self.activated_content_corrected,
        }


@dataclass
class ActivationTrace:
    """Trace entry for activation events."""
    source_id: str
    neighbor_id: str
    activation_strength: float
    blocked: bool
    reason: str | None = None
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "neighbor_id": self.neighbor_id,
            "activation_strength": self.activation_strength,
            "blocked": self.blocked,
            "reason": self.reason,
        }


@dataclass
class MemoryDynamicsEvent:
    """A memory dynamics event for tracing and auditing."""
    schema_version: str = "1.0"
    event_id: str = ""
    mechanism: MemoryMechanism = MemoryMechanism.DECAY
    source_candidate: SourceCandidate = SourceCandidate.INTERNAL
    input_refs: list[str] = field(default_factory=list)
    output_refs: list[str] = field(default_factory=list)
    confidence_before: float | None = None
    confidence_after: float | None = None
    salience_before: float | None = None
    salience_after: float | None = None
    privacy_status: str | None = None
    correction_status: CorrectionStatus = CorrectionStatus.NONE
    decision: DecisionOutcome = DecisionOutcome.ALLOW
    reasons: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "mechanism": self.mechanism.value,
            "source_candidate": self.source_candidate.value,
            "input_refs": self.input_refs,
            "output_refs": self.output_refs,
            "confidence_before": self.confidence_before,
            "confidence_after": self.confidence_after,
            "salience_before": self.salience_before,
            "salience_after": self.salience_after,
            "privacy_status": self.privacy_status,
            "correction_status": self.correction_status.value,
            "decision": self.decision.value,
            "reasons": self.reasons,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class DecayConfig:
    """Configuration for memory decay mechanism."""
    decay_rate: float = 0.95
    salience_threshold: float = 0.1
    rehearsal_boost: float = 0.1
    max_salience: float = 1.0
    min_salience: float = 0.0
    config_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "decay_rate": self.decay_rate,
            "salience_threshold": self.salience_threshold,
            "rehearsal_boost": self.rehearsal_boost,
            "max_salience": self.max_salience,
            "min_salience": self.min_salience,
            "config_id": self.config_id,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DecayConfig:
        return cls(
            decay_rate=data["decay_rate"],
            salience_threshold=data["salience_threshold"],
            rehearsal_boost=data["rehearsal_boost"],
            max_salience=data["max_salience"],
            min_salience=data["min_salience"],
            config_id=data["config_id"],
            metadata=data.get("metadata", {}),
        )


@dataclass
class SourceRef:
    """Reference to the source of a consolidated memory."""
    source_id: str
    source_type: str
    original_hash: str
    timestamp: datetime


@dataclass
class ConsolidatedMemory:
    """A memory created by consolidating multiple source memories."""
    consolidated_id: str
    content_hash: str
    source_refs: list[SourceRef]
    created_at: datetime
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "consolidated_id": self.consolidated_id,
            "content_hash": self.content_hash,
            "source_refs": [
                {
                    "source_id": ref.source_id,
                    "source_type": ref.source_type,
                    "original_hash": ref.original_hash,
                    "timestamp": ref.timestamp.isoformat(),
                }
                for ref in self.source_refs
            ],
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class MemoryUpdateEvent:
    """A memory update event in the audit history."""
    event_id: str
    timestamp: datetime
    event_type: str
    block_id: str
    content_hash: str
    previous_hash: str | None = None
    source_lineage: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type,
            "block_id": self.block_id,
            "content_hash": self.content_hash,
            "previous_hash": self.previous_hash,
            "source_lineage": self.source_lineage,
            "metadata": self.metadata,
        }
