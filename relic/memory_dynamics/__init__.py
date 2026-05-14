"""Memory dynamics module for deterministic memory management.

This module implements memory dynamics mechanisms:
- Decay: Deterministic salience reduction based on time
- Reinforcement: Salience increase without overriding corrections
- Association: Scoped spreading activation with privacy/correction gates
- Consolidation: Memory merging with preserved source lineage
- Projection: Redacted human-readable memory summaries

All mechanisms produce mechanism reports and never alter runtime behavior
before promotion gates.
"""

from __future__ import annotations

from relic.memory_dynamics.association import AssociationTracer, ScopeGate
from relic.memory_dynamics.consolidation import MemoryConsolidator
from relic.memory_dynamics.decay import MemoryDecay
from relic.memory_dynamics.projection import ProjectionGenerator, RedactedProjection
from relic.memory_dynamics.reinforcement import MemoryReinforcement
from relic.memory_dynamics.service import MemoryDynamicsService
from relic.memory_dynamics.store import MemoryDynamicsStore
from relic.memory_dynamics.types import (
    ActivationTrace,
    ConsolidatedMemory,
    CorrectionStatus,
    DecayConfig,
    DecisionOutcome,
    MemoryDynamicsEvent,
    MemoryMechanism,
    SalienceLevel,
    SalienceResult,
    SourceCandidate,
    SourceRef,
)

__all__ = [
    # Core service
    "MemoryDynamicsService",
    
    # Mechanisms
    "MemoryDecay",
    "MemoryReinforcement",
    "MemoryConsolidator",
    "ScopeGate",
    "AssociationTracer",
    "ProjectionGenerator",
    
    # Types
    "MemoryDynamicsEvent",
    "MemoryMechanism",
    "SourceCandidate",
    "DecisionOutcome",
    "SalienceLevel",
    "SalienceResult",
    "DecayConfig",
    "ConsolidatedMemory",
    "SourceRef",
    "ActivationTrace",
    "SpreadingActivationResult",
    "CorrectionStatus",
    "RedactedProjection",
    "MemoryDynamicsStore",
]
