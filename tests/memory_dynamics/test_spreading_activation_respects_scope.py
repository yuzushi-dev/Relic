"""Tests for spreading activation respects scope.

Acceptance criteria:
- graph activation cannot bypass scope privacy or correction gates
- mechanism report outputs remain mechanism reports
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import uuid4

import pytest

from relic.memory_dynamics import ScopeGate


class TestSpreadingActivationRespectsScope:
    """Tests verifying spreading activation respects scope gates."""

    def test_activation_blocked_by_privacy_gate(self, tmp_path: Path) -> None:
        """Test activation is blocked when source has S0 privacy violation."""
        gate = ScopeGate()

        source_memory = {
            "id": str(uuid4()),
            "content_hash": hashlib.sha256(b"secret").hexdigest(),
            "privacy_level": "S0_HARD_VIOLATION",
        }

        neighbor_memory = {
            "id": str(uuid4()),
            "content_hash": hashlib.sha256(b"neighbor").hexdigest(),
        }

        result = gate.check_spreading_activation(
            source_memory=source_memory,
            neighbor_memory=neighbor_memory,
            activation_strength=0.8,
        )

        assert result.allowed is False
        assert result.blocked_by == "privacy_gate"
        assert result.correction_respected is True

    def test_activation_blocked_by_correction_gate(self, tmp_path: Path) -> None:
        """Test activation is blocked when source has active correction."""
        gate = ScopeGate()

        source_memory = {
            "id": str(uuid4()),
            "content_hash": hashlib.sha256(b"old fact").hexdigest(),
            "correction_active": True,
            "corrected_content": "new fact",
        }

        neighbor_memory = {
            "id": str(uuid4()),
            "content_hash": hashlib.sha256(b"neighbor").hexdigest(),
        }

        result = gate.check_spreading_activation(
            source_memory=source_memory,
            neighbor_memory=neighbor_memory,
            activation_strength=0.9,
        )

        assert result.allowed is False
        assert result.blocked_by == "correction_gate"
        assert result.correction_respected is True

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
        """Test that privacy trace does not contain raw sensitive text."""
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

        assert "secret@example.com" not in trace_json
        assert "email:" not in trace_json

    def test_activation_produces_mechanism_report_not_runtime_change(self, tmp_path: Path) -> None:
        """Test activation produces mechanism report, not runtime behavior change."""
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

        result_dict = result.to_dict()
        assert "runtime_behavior_changed" not in result_dict
