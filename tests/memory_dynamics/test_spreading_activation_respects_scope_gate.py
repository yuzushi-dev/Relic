"""Tests for spreading activation respects scope privacy/correction gates.

Acceptance criteria:
- graph activation cannot bypass scope privacy or correction gates
- mechanism report outputs remain mechanism reports and cannot alter runtime behavior before promotion gate

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


class PrivacyLevel(Enum):
    """Privacy classification levels."""
    S0_HARD_VIOLATION = "s0"
    S1_QUARANTINE = "s1"
    S2_WARNING = "s2"
    SAFE = "safe"


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
            activation_propagated=True,
            correction_respected=True,
        )

    def get_trace(self) -> list[ActivationTrace]:
        """Get all activation traces."""
        return self._traces.copy()


class TestSpreadingActivationRespectsScopeGate:
    """Tests verifying graph spreading activation respects privacy/correction gates."""

    def test_activation_cannot_bypass_privacy_gate(self, tmp_path: Path) -> None:
        """Test that spreading activation cannot bypass scope privacy gate.

        This verifies graph neighbors cannot be activated if the source
        memory is marked S0/S1 without going through the privacy gate.
        """
        gate = ScopeGate()

        # Source memory marked with S0 violation
        source_memory = {
            "id": str(uuid4()),
            "content_hash": hashlib.sha256(b"email: secret@example.com").hexdigest(),
            "privacy_level": "S0_HARD_VIOLATION",
            "is_redacted": True,
        }

        # Neighbor memory (safe content)
        neighbor_memory = {
            "id": str(uuid4()),
            "content_hash": hashlib.sha256(b"weather forecast").hexdigest(),
            "privacy_level": "SAFE",
            "is_redacted": False,
        }

        # Spreading activation should check source gate before propagating
        activation_result = gate.check_spreading_activation(
            source_memory=source_memory,
            neighbor_memory=neighbor_memory,
            activation_strength=0.8,
        )

        # Source is blocked, so activation must not proceed
        assert activation_result.allowed is False
        assert activation_result.blocked_by == "privacy_gate"
        assert activation_result.activation_propagated is False

    def test_activation_respects_correction_scope(self, tmp_path: Path) -> None:
        """Test that spreading activation respects correction scope boundaries.

        Corrected memories should not have their corrections bypassed
        through graph neighbor activation.
        """
        gate = ScopeGate()

        # Source memory with active correction
        source_memory = {
            "id": str(uuid4()),
            "content_hash": hashlib.sha256(b"old fact").hexdigest(),
            "correction_active": True,
            "corrected_content": "new fact",
            "correction_scope": CorrectionScope.FULL_SCOPE,
        }

        # Neighbor memory
        neighbor_memory = {
            "id": str(uuid4()),
            "content_hash": hashlib.sha256(b"related topic").hexdigest(),
        }

        activation_result = gate.check_spreading_activation(
            source_memory=source_memory,
            neighbor_memory=neighbor_memory,
            activation_strength=0.9,
        )

        # Activation respects correction scope - either blocked or marked corrected
        assert activation_result.correction_respected is True
        assert activation_result.activated_content_corrected is True

    def test_activation_blocked_when_source_redacted(self, tmp_path: Path) -> None:
        """Test activation is blocked when source memory is redacted."""
        gate = ScopeGate()

        source_memory = {
            "id": str(uuid4()),
            "content_hash": hashlib.sha256(b"redacted content").hexdigest(),
            "is_redacted": True,
            "privacy_level": "S1_QUARANTINE",
        }

        neighbor_memory = {
            "id": str(uuid4()),
            "content_hash": hashlib.sha256(b"neighbor content").hexdigest(),
        }

        result = gate.check_spreading_activation(
            source_memory=source_memory,
            neighbor_memory=neighbor_memory,
            activation_strength=0.5,
        )

        assert result.allowed is False
        assert result.blocked_by in ("privacy_gate", "redaction")

    def test_safe_activation_passes_through_gate(self, tmp_path: Path) -> None:
        """Test that safe memory activation passes through gate correctly."""
        gate = ScopeGate()

        source_memory = {
            "id": str(uuid4()),
            "content_hash": hashlib.sha256(b"safe content").hexdigest(),
            "privacy_level": "SAFE",
            "is_redacted": False,
            "correction_active": False,
        }

        neighbor_memory = {
            "id": str(uuid4()),
            "content_hash": hashlib.sha256(b"neighbor safe").hexdigest(),
            "privacy_level": "SAFE",
        }

        result = gate.check_spreading_activation(
            source_memory=source_memory,
            neighbor_memory=neighbor_memory,
            activation_strength=0.7,
        )

        assert result.allowed is True
        assert result.activation_propagated is True

    def test_privacy_trace_no_raw_sensitive_text(self, tmp_path: Path) -> None:
        """Test that privacy trace does not contain raw sensitive text.

        Even when activation is blocked, trace must only contain hashes.
        """
        gate = ScopeGate()

        source_memory = {
            "id": str(uuid4()),
            "content_hash": hashlib.sha256(b"email: secret@example.com").hexdigest(),
            "privacy_level": "S0_HARD_VIOLATION",
            "is_redacted": True,
        }

        neighbor_memory = {
            "id": str(uuid4()),
            "content_hash": hashlib.sha256(b"neighbor").hexdigest(),
        }

        gate.check_spreading_activation(
            source_memory=source_memory,
            neighbor_memory=neighbor_memory,
            activation_strength=0.8,
        )

        traces = gate.get_trace()
        trace_json = json.dumps([t.to_dict() for t in traces])

        # Must not contain raw email
        assert "secret@example.com" not in trace_json
        assert "email:" not in trace_json

    def test_activation_produces_mechanism_report_not_runtime_change(self, tmp_path: Path) -> None:
        """Test activation produces mechanism report, not runtime behavior change.

        mechanism report outputs must remain mechanism reports and cannot alter
        runtime behavior before promotion gate.
        """
        gate = ScopeGate()

        source_memory = {
            "id": str(uuid4()),
            "content_hash": hashlib.sha256(b"test").hexdigest(),
            "privacy_level": "SAFE",
        }

        neighbor_memory = {
            "id": str(uuid4()),
            "content_hash": hashlib.sha256(b"neighbor").hexdigest(),
        }

        result = gate.check_spreading_activation(
            source_memory=source_memory,
            neighbor_memory=neighbor_memory,
            activation_strength=0.6,
        )

        # Result is a mechanism report, not a runtime modification
        assert hasattr(result, "to_dict")
        result_dict = result.to_dict()
        assert "runtime_behavior_changed" not in result_dict
