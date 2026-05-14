"""Memory association and spreading activation mechanism.

This module implements scoped spreading activation that respects privacy
and correction boundaries.
"""

from __future__ import annotations

import hashlib
from typing import Any

from relic.memory_dynamics.types import (
    ActivationTrace,
    SpreadingActivationResult,
)


class ScopeGate:
    """Scope gate for spreading activation.
    
    This class provides the interface for checking whether spreading
    activation can propagate through graph neighbors while respecting
    privacy and correction boundaries.
    """

    def __init__(self):
        self._traces: list[ActivationTrace] = []

    def check_spreading_activation(
        self,
        source_memory: dict[str, Any],
        neighbor_memory: dict[str, Any],
        activation_strength: float,
    ) -> SpreadingActivationResult:
        """Check if spreading activation should propagate from source to neighbor.
        
        BLOCKS activation when:
        - Source memory is S0 or S1 without going through privacy gate
        - Source memory has active correction
        - Any memory is redacted
        """
        source_privacy = source_memory.get("privacy_level", "SAFE")
        source_redacted = source_memory.get("is_redacted", False)
        source_correction = source_memory.get("correction_active", False)
        
        neighbor_correction = neighbor_memory.get("correction_active", False)
        
        # Block if source is blocked by privacy
        if source_privacy in ("S0_HARD_VIOLATION", "S0", "s0", "S1_QUARANTINE", "S1", "s1"):
            trace = ActivationTrace(
                source_id=source_memory.get("id", "unknown"),
                neighbor_id=neighbor_memory.get("id", "unknown"),
                activation_strength=activation_strength,
                blocked=True,
                reason="privacy_gate",
            )
            self._traces.append(trace)
            return SpreadingActivationResult(
                allowed=False,
                blocked_by="privacy_gate",
                activation_propagated=False,
                correction_respected=True,
            )
        
        # Block if source is redacted
        if source_redacted:
            trace = ActivationTrace(
                source_id=source_memory.get("id", "unknown"),
                neighbor_id=neighbor_memory.get("id", "unknown"),
                activation_strength=activation_strength,
                blocked=True,
                reason="redaction",
            )
            self._traces.append(trace)
            return SpreadingActivationResult(
                allowed=False,
                blocked_by="redaction",
                activation_propagated=False,
                correction_respected=True,
            )
        
        # Block if source has active correction
        if source_correction:
            trace = ActivationTrace(
                source_id=source_memory.get("id", "unknown"),
                neighbor_id=neighbor_memory.get("id", "unknown"),
                activation_strength=activation_strength,
                blocked=True,
                reason="correction_scope",
            )
            self._traces.append(trace)
            return SpreadingActivationResult(
                allowed=False,
                blocked_by="correction_gate",
                activation_propagated=False,
                correction_respected=True,
                activated_content_corrected=True,
            )
        
        # Block if NEIGHBOR has active correction (prevent reactivation)
        if neighbor_correction:
            trace = ActivationTrace(
                source_id=source_memory.get("id", "unknown"),
                neighbor_id=neighbor_memory.get("id", "unknown"),
                activation_strength=activation_strength,
                blocked=True,
                reason="neighbor_correction",
            )
            self._traces.append(trace)
            return SpreadingActivationResult(
                allowed=False,
                blocked_by="correction_gate",
                activation_propagated=False,
                correction_respected=True,
                activated_content_corrected=True,
            )
        
        # Safe to propagate
        trace = ActivationTrace(
            source_id=source_memory.get("id", "unknown"),
            neighbor_id=neighbor_memory.get("id", "unknown"),
            activation_strength=activation_strength,
            blocked=False,
        )
        self._traces.append(trace)
        return SpreadingActivationResult(
            allowed=True,
            activation_propagated=True,
            correction_respected=True,
        )

    def get_trace(self) -> list[ActivationTrace]:
        """Get all activation traces."""
        return self._traces.copy()

    def clear_trace(self) -> None:
        """Clear activation traces."""
        self._traces.clear()


class AssociationTracer:
    """Tracer for memory associations that explains activation paths."""
    
    def __init__(self):
        self._associations: list[dict[str, Any]] = []
    
    def record_association(
        self,
        source_id: str,
        target_id: str,
        association_type: str,
        strength: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Record an association between two memory blocks.
        
        Returns the association record.
        """
        # Store hash of IDs, not raw IDs
        record = {
            "source_hash": hashlib.sha256(source_id.encode()).hexdigest()[:16],
            "target_hash": hashlib.sha256(target_id.encode()).hexdigest()[:16],
            "association_type": association_type,
            "strength": strength,
            "metadata": metadata or {},
        }
        self._associations.append(record)
        return record
    
    def get_associations(self, source_id: str | None = None) -> list[dict[str, Any]]:
        """Get associations, optionally filtered by source."""
        if source_id is None:
            return self._associations.copy()
        
        source_hash = hashlib.sha256(source_id.encode()).hexdigest()[:16]
        return [
            a for a in self._associations
            if a["source_hash"] == source_hash
        ]
    
    def explain_path(self, memory_ids: list[str]) -> list[str]:
        """Explain the association path between memory blocks."""
        explanations = []
        for i, mem_id in enumerate(memory_ids):
            if i > 0:
                prev_id = memory_ids[i - 1]
                associations = self.get_associations(prev_id)
                for assoc in associations:
                    if assoc["target_hash"] == hashlib.sha256(mem_id.encode()).hexdigest()[:16]:
                        explanations.append(
                            f"via {assoc['association_type']} (strength: {assoc['strength']})"
                        )
        return explanations
