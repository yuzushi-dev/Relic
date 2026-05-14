"""Memory dynamics service orchestrating all mechanisms.

This module provides a unified service that orchestrates all memory
dynamics mechanisms: decay, reinforcement, association, consolidation,
and projection.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from relic.memory_dynamics.association import AssociationTracer, ScopeGate
from relic.memory_dynamics.consolidation import MemoryConsolidator
from relic.memory_dynamics.decay import MemoryDecay
from relic.memory_dynamics.projection import ProjectionGenerator
from relic.memory_dynamics.reinforcement import MemoryReinforcement
from relic.memory_dynamics.store import MemoryDynamicsStore
from relic.memory_dynamics.types import (
    DecisionOutcome,
    MemoryDynamicsEvent,
    MemoryMechanism,
    SalienceLevel,
    SalienceResult,
    SourceCandidate,
)
from relic.persistence import MemoryPersistence, PrivacyLevel


class MemoryDynamicsService:
    """Orchestrating service for memory dynamics.
    
    This service provides a unified interface for all memory dynamics
    mechanisms while maintaining proper audit trails and respecting
    privacy/correction boundaries.
    """

    def __init__(self, persistence: MemoryPersistence | None = None):
        self._persistence = persistence or MemoryPersistence()
        self._store = MemoryDynamicsStore(self._persistence)
        
        # Initialize mechanisms
        self._decay = MemoryDecay()
        self._reinforcement = MemoryReinforcement()
        self._consolidator = MemoryConsolidator(self._persistence)
        self._projection = ProjectionGenerator()
        self._scope_gate = ScopeGate()
        self._association_tracer = AssociationTracer()
        
        # Memory state
        self._memories: dict[str, dict[str, Any]] = {}

    # === Decay Operations ===
    
    def calculate_decay(self, memory: dict[str, Any]) -> SalienceResult:
        """Calculate decayed salience for a memory."""
        result = self._decay.calculate_salience(memory)
        
        # Record event
        self._record_event(
            mechanism=MemoryMechanism.DECAY,
            input_refs=[memory.get("id", "unknown")],
            salience_before=memory.get("salience", 1.0),
            salience_after=result.salience_score,
            decision=DecisionOutcome.ALLOW,
            reasons=["decay_applied"],
        )
        
        return result

    def apply_decay(
        self,
        memory_id: str,
        time_delta_hours: float = 1.0,
    ) -> float | None:
        """Apply decay to a memory's salience."""
        memory = self._memories.get(memory_id)
        if not memory:
            return None
        
        current_salience = memory.get("salience", 0.5)
        new_salience = self._decay.apply_decay(current_salience, time_delta_hours)
        memory["salience"] = new_salience
        
        return new_salience

    # === Reinforcement Operations ===
    
    def apply_reinforcement(
        self,
        memory_id: str,
    ) -> dict[str, Any] | None:
        """Apply reinforcement to a memory."""
        memory = self._memories.get(memory_id)
        if not memory:
            return None
        
        result = self._reinforcement.rehearsal(memory_id, memory)
        
        # Update memory salience
        memory["salience"] = result["salience_after"]
        memory["rehearsal_count"] = result["rehearsal_count"]
        
        # Record event
        self._record_event(
            mechanism=MemoryMechanism.REINFORCEMENT,
            input_refs=[memory_id],
            salience_before=result["salience_before"],
            salience_after=result["salience_after"],
            decision=DecisionOutcome.ALLOW,
            reasons=["reinforcement_applied"],
        )
        
        return result

    # === Association Operations ===
    
    def check_activation(
        self,
        source_memory: dict[str, Any],
        neighbor_memory: dict[str, Any],
        activation_strength: float = 0.5,
    ) -> bool:
        """Check if spreading activation can propagate."""
        result = self._scope_gate.check_spreading_activation(
            source_memory,
            neighbor_memory,
            activation_strength,
        )
        
        # Record event
        self._record_event(
            mechanism=MemoryMechanism.ASSOCIATION,
            input_refs=[
                source_memory.get("id", "unknown"),
                neighbor_memory.get("id", "unknown"),
            ],
            decision=DecisionOutcome.ALLOW if result.allowed else DecisionOutcome.BLOCK,
            reasons=[result.blocked_by] if result.blocked_by else ["activation_allowed"],
        )
        
        return result.allowed

    def record_association(
        self,
        source_id: str,
        target_id: str,
        association_type: str,
        strength: float = 1.0,
    ) -> dict[str, Any]:
        """Record an association between memories."""
        return self._association_tracer.record_association(
            source_id,
            target_id,
            association_type,
            strength,
        )

    # === Consolidation Operations ===
    
    def consolidate_memories(
        self,
        source_ids: list[str],
        values: list[str],
        source_type: str = "interaction",
    ) -> dict[str, Any] | None:
        """Consolidate multiple memories preserving source lineage."""
        if len(source_ids) != len(values):
            return None
        
        consolidated = self._consolidator.consolidate(
            source_ids=source_ids,
            source_type=source_type,
            values=values,
        )
        
        # Record event
        self._record_event(
            mechanism=MemoryMechanism.CONSOLIDATION,
            input_refs=source_ids,
            output_refs=[consolidated.consolidated_id],
            decision=DecisionOutcome.ALLOW,
            reasons=["consolidation_complete", "lineage_preserved"],
        )
        
        return consolidated.to_dict()

    # === Projection Operations ===
    
    def generate_projection(
        self,
        memory_id: str,
        content: str,
        privacy_level: str = "SAFE",
    ) -> dict[str, Any]:
        """Generate a redacted human-readable projection."""
        projection = self._projection.generate_projection(
            memory_id=memory_id,
            content=content,
            privacy_level=privacy_level,
        )
        
        return projection.to_dict()

    # === Memory Management ===
    
    def register_memory(
        self,
        memory_id: str,
        content: str,
        salience: float = 0.5,
        privacy_level: PrivacyLevel = PrivacyLevel.SAFE,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Register a new memory in the dynamics system."""
        memory = {
            "id": memory_id,
            "content": content,
            "salience": salience,
            "privacy_level": privacy_level.value,
            "created_at": datetime.utcnow(),
            "last_accessed": datetime.utcnow(),
            "access_count": 0,
            "correction_active": False,
            "is_redacted": False,
            "metadata": metadata or {},
        }
        
        self._memories[memory_id] = memory
        
        # Store in persistence
        self._persistence.store(content, privacy_level, metadata)
        
        return memory

    def get_memory(self, memory_id: str) -> dict[str, Any] | None:
        """Get a memory by ID."""
        memory = self._memories.get(memory_id)
        if memory:
            # Update access tracking
            memory["last_accessed"] = datetime.utcnow()
            memory["access_count"] = memory.get("access_count", 0) + 1
        return memory

    def set_correction_active(self, memory_id: str, active: bool = True) -> bool:
        """Set correction status on a memory."""
        memory = self._memories.get(memory_id)
        if not memory:
            return False
        memory["correction_active"] = active
        return True

    # === Event Recording ===
    
    def _record_event(
        self,
        mechanism: MemoryMechanism,
        input_refs: list[str],
        output_refs: list[str] | None = None,
        salience_before: float | None = None,
        salience_after: float | None = None,
        decision: DecisionOutcome = DecisionOutcome.ALLOW,
        reasons: list[str] | None = None,
    ) -> MemoryDynamicsEvent:
        """Record a memory dynamics event."""
        event = MemoryDynamicsEvent(
            event_id=f"MDYN-{uuid4().hex[:8]}",
            mechanism=mechanism,
            source_candidate=SourceCandidate.INTERNAL,
            input_refs=input_refs,
            output_refs=output_refs or [],
            salience_before=salience_before,
            salience_after=salience_after,
            decision=decision,
            reasons=reasons or [],
        )
        
        self._store.store_event(event)
        return event

    def get_events(self, mechanism: str | None = None) -> list[MemoryDynamicsEvent]:
        """Get memory dynamics events."""
        return self._store.get_events(mechanism=mechanism)

    def get_trace(self) -> list[MemoryDynamicsEvent]:
        """Get full event trace."""
        return self._store.get_trace()

    # === Getters for mechanisms ===
    
    @property
    def decay(self) -> MemoryDecay:
        """Get the decay mechanism."""
        return self._decay

    @property
    def reinforcement(self) -> MemoryReinforcement:
        """Get the reinforcement mechanism."""
        return self._reinforcement

    @property
    def consolidator(self) -> MemoryConsolidator:
        """Get the consolidator."""
        return self._consolidator

    @property
    def projection(self) -> ProjectionGenerator:
        """Get the projection generator."""
        return self._projection

    @property
    def scope_gate(self) -> ScopeGate:
        """Get the scope gate."""
        return self._scope_gate
