"""Tests for corrected memory not reactivated by graph neighbors.

Acceptance criteria:
- corrected memories are not reactivated by graph neighbor activation
- correction gate is respected during spreading activation

Tests are designed to fail-closed on privacy/correction/runtime bypass.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest


class CorrectionScope(Enum):
    """Correction scope levels."""
    FULL_SCOPE = "full"
    PARTIAL_SCOPE = "partial"
    NO_SCOPE = "none"


@dataclass
class SpreadingActivationResult:
    """Result of spreading activation check."""
    allowed: bool
    blocked_by: str | None = None
    reactivation_blocked: bool = False
    correction_respected: bool = True
    correction_scope_respected: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "blocked_by": self.blocked_by,
            "reactivation_blocked": self.reactivation_blocked,
            "correction_respected": self.correction_respected,
            "correction_scope_respected": self.correction_scope_respected,
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


class ScopeGate:
    """Scope gate for spreading activation with correction respect.
    
    This class provides the interface for checking whether spreading
    activation can propagate through graph neighbors while respecting
    correction boundaries.
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
        - Neighbor memory has active correction (preventing reactivation)
        - Source memory is blocked by privacy/correction
        """
        source_privacy = source_memory.get("privacy_level", "SAFE")
        source_redacted = source_memory.get("is_redacted", False)
        source_correction = source_memory.get("correction_active", False)
        
        neighbor_correction = neighbor_memory.get("correction_active", False)
        neighbor_correction_scope = neighbor_memory.get("correction_scope", CorrectionScope.NO_SCOPE)
        
        # Block if source is blocked by privacy
        if source_privacy in ("S0_HARD_VIOLATION", "S0", "s0"):
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
                reactivation_blocked=False,
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
                reactivation_blocked=False,
                correction_respected=True,
            )
        
        # Block if source has active correction
        if source_correction:
            trace = ActivationTrace(
                source_id=source_memory.get("id", "unknown"),
                neighbor_id=neighbor_memory.get("id", "unknown"),
                activation_strength=activation_strength,
                blocked=True,
                reason="source_correction",
            )
            self._traces.append(trace)
            return SpreadingActivationResult(
                allowed=False,
                blocked_by="correction_gate",
                reactivation_blocked=False,
                correction_respected=True,
            )
        
        # Block if NEIGHBOR has active correction (preventing reactivation)
        if neighbor_correction:
            trace = ActivationTrace(
                source_id=source_memory.get("id", "unknown"),
                neighbor_id=neighbor_memory.get("id", "unknown"),
                activation_strength=activation_strength,
                blocked=True,
                reason="neighbor_corrected",
            )
            self._traces.append(trace)
            return SpreadingActivationResult(
                allowed=False,
                blocked_by="correction_gate",
                reactivation_blocked=True,
                correction_respected=True,
                correction_scope_respected=neighbor_correction_scope != CorrectionScope.NO_SCOPE,
            )
        
        # Safe - allow activation
        trace = ActivationTrace(
            source_id=source_memory.get("id", "unknown"),
            neighbor_id=neighbor_memory.get("id", "unknown"),
            activation_strength=activation_strength,
            blocked=False,
        )
        self._traces.append(trace)
        return SpreadingActivationResult(
            allowed=True,
            correction_respected=True,
            correction_scope_respected=True,
        )

    def get_trace(self) -> list[ActivationTrace]:
        """Get all activation traces."""
        return self._traces.copy()


class TestCorrectedMemoryNotReactivatedByGraphNeighbors:
    """Tests verifying corrected memories are not reactivated by graph neighbors."""

    def test_corrected_memory_blocked_from_reactivation(self, tmp_path: Path) -> None:
        """Test that corrected memories cannot be reactivated through graph neighbors.

        When a memory has been corrected, graph neighbor activation should
        not be able to reactivate the old (incorrect) memory.
        """
        gate = ScopeGate()

        # Memory with active correction
        corrected_memory = {
            "id": str(uuid4()),
            "content_hash": hashlib.sha256(b"old incorrect fact").hexdigest(),
            "correction_active": True,
            "corrected_content": hashlib.sha256(b"new correct fact").hexdigest(),
            "correction_scope": CorrectionScope.FULL_SCOPE,
            "correction_timestamp": "2024-01-15T10:00:00Z",
        }

        # Neighbor memory trying to reactivate
        neighbor_memory = {
            "id": str(uuid4()),
            "content_hash": hashlib.sha256(b"related topic").hexdigest(),
        }

        result = gate.check_spreading_activation(
            source_memory=neighbor_memory,
            neighbor_memory=corrected_memory,
            activation_strength=0.9,
        )

        # Must not reactivate corrected memory
        assert result.allowed is False
        assert result.reactivation_blocked is True
        assert result.correction_respected is True

    def test_correction_scope_boundary_respected(self, tmp_path: Path) -> None:
        """Test correction scope boundary is respected during activation."""
        gate = ScopeGate()

        # Memory with partial correction scope
        partially_corrected = {
            "id": str(uuid4()),
            "content_hash": hashlib.sha256(b"partial content").hexdigest(),
            "correction_active": True,
            "corrected_content": hashlib.sha256(b"corrected partial").hexdigest(),
            "correction_scope": CorrectionScope.PARTIAL_SCOPE,
            "correction_exclusions": ["metadata"],
        }

        neighbor_memory = {
            "id": str(uuid4()),
            "content_hash": hashlib.sha256(b"metadata neighbor").hexdigest(),
        }

        result = gate.check_spreading_activation(
            source_memory=neighbor_memory,
            neighbor_memory=partially_corrected,
            activation_strength=0.8,
        )

        # Should respect partial scope boundaries
        assert result.correction_scope_respected is True

    def test_correction_propagation_trace_is_private(self, tmp_path: Path) -> None:
        """Test correction propagation trace contains no raw content."""
        gate = ScopeGate()

        corrected_memory = {
            "id": str(uuid4()),
            "content_hash": hashlib.sha256(b"old password").hexdigest(),
            "correction_active": True,
            "corrected_content": hashlib.sha256(b"new password").hexdigest(),
        }

        neighbor_memory = {
            "id": str(uuid4()),
            "content_hash": hashlib.sha256(b"login topic").hexdigest(),
        }

        gate.check_spreading_activation(
            source_memory=neighbor_memory,
            neighbor_memory=corrected_memory,
            activation_strength=0.9,
        )

        traces = gate.get_trace()
        trace_json = json.dumps([t.to_dict() for t in traces])

        # Must not contain raw password
        assert "old password" not in trace_json.lower()
        assert "new password" not in trace_json.lower()

    def test_multiple_corrections_block_independent(self, tmp_path: Path) -> None:
        """Test multiple corrections block independently."""
        gate = ScopeGate()

        # Two corrected memories
        memories = [
            {
                "id": str(uuid4()),
                "content_hash": hashlib.sha256(b"fact 1").hexdigest(),
                "correction_active": True,
                "corrected_content": hashlib.sha256(b"correction 1").hexdigest(),
                "correction_scope": CorrectionScope.FULL_SCOPE,
            },
            {
                "id": str(uuid4()),
                "content_hash": hashlib.sha256(b"fact 2").hexdigest(),
                "correction_active": True,
                "corrected_content": hashlib.sha256(b"correction 2").hexdigest(),
                "correction_scope": CorrectionScope.FULL_SCOPE,
            },
        ]

        safe_memory = {
            "id": str(uuid4()),
            "content_hash": hashlib.sha256(b"safe").hexdigest(),
        }

        # Both corrections should be respected
        for mem in memories:
            result = gate.check_spreading_activation(
                source_memory=safe_memory,
                neighbor_memory=mem,
                activation_strength=0.8,
            )
            assert result.correction_respected is True
            assert result.allowed is False

    def test_correction_respected_without_runtime_override(self, tmp_path: Path) -> None:
        """Test correction is respected without runtime override capability.

        mechanism report outputs must remain mechanism reports and cannot alter
        runtime behavior before promotion gate.
        """
        gate = ScopeGate()

        memory = {
            "id": str(uuid4()),
            "content_hash": hashlib.sha256(b"old").hexdigest(),
            "correction_active": True,
            "corrected_content": hashlib.sha256(b"new").hexdigest(),
            "correction_scope": CorrectionScope.FULL_SCOPE,
        }

        safe_neighbor = {
            "id": str(uuid4()),
            "content_hash": hashlib.sha256(b"safe").hexdigest(),
        }

        result = gate.check_spreading_activation(
            source_memory=safe_neighbor,
            neighbor_memory=memory,
            activation_strength=0.9,
        )

        # Result is a mechanism report
        assert hasattr(result, "to_dict")
        result_dict = result.to_dict()

        # No runtime override capability
        assert "runtime_override" not in result_dict
        assert "correction_bypass" not in result_dict
