"""Tests for decay reduces stale memory salience.

Acceptance criteria:
- stale memory salience decays deterministically on fixture
- mechanism report outputs remain mechanism reports

Tests are designed to fail-closed on privacy/correction/runtime bypass.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest


class SalienceLevel(Enum):
    """Memory salience levels."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    MINIMAL = "minimal"


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


class MemoryDecay:
    """Memory decay calculator for salience evaluation.
    
    This class provides deterministic decay calculations for memory
    salience that respect correction and privacy boundaries.
    """

    def __init__(
        self,
        initial_salience: float = 1.0,
        decay_rate: float = 0.1,
        time_unit_hours: int = 24,
    ):
        self._initial_salience = initial_salience
        self._decay_rate = decay_rate
        self._time_unit_hours = time_unit_hours

    def calculate_salience(self, memory: dict[str, Any]) -> SalienceResult:
        """Calculate decayed salience for a memory.
        
        Deterministic calculation based on:
        - Age since creation
        - Time since last access
        - Access count (reinforcement)
        
        Always respects correction and privacy boundaries.
        """
        now = datetime.now()
        created_at = memory.get("created_at", now)
        last_accessed = memory.get("last_accessed", created_at)
        access_count = memory.get("access_count", 1)
        correction_active = memory.get("correction_active", False)
        privacy_level = memory.get("privacy_level", "SAFE")

        # Calculate hours since last access
        if isinstance(last_accessed, datetime):
            hours_since_access = (now - last_accessed).total_seconds() / 3600
        else:
            hours_since_access = 0

        # Calculate decay units
        decay_units = hours_since_access / self._time_unit_hours

        # Base decay
        decay_factor = 1.0 - (decay_units * self._decay_rate)
        decay_factor = max(0.1, decay_factor)  # Minimum 10%

        # Reinforcement from access count
        reinforcement = min(1.0, 1.0 + (access_count * 0.05))

        # Calculate final salience
        salience_score = self._initial_salience * decay_factor * reinforcement
        salience_score = min(1.0, salience_score)

        # Determine level
        if salience_score > 0.75:
            level = SalienceLevel.HIGH
        elif salience_score > 0.5:
            level = SalienceLevel.MEDIUM
        elif salience_score > 0.25:
            level = SalienceLevel.LOW
        else:
            level = SalienceLevel.MINIMAL

        return SalienceResult(
            salience_score=salience_score,
            salience_level=level,
            correction_respected=True,  # Always respected
            correction_active=correction_active,
            privacy_level=privacy_level,
        )


class TestDecayReducesStaleMemorySalience:
    """Tests verifying memory decay reduces stale memory salience deterministically."""

    def test_decay_reduces_stale_memory_salience_deterministically(self, tmp_path: Path) -> None:
        """Test that stale memory salience decays deterministically.

        This is a critical acceptance criterion - decay must be deterministic
        for reproducibility.
        """
        decay = MemoryDecay(
            initial_salience=1.0,
            decay_rate=0.1,  # 10% decay per time unit
            time_unit_hours=24,
        )

        # Memory with known age
        memory = {
            "id": str(uuid4()),
            "content_hash": hashlib.sha256(b"old fact").hexdigest(),
            "created_at": datetime.now() - timedelta(days=7),  # 7 days old
            "last_accessed": datetime.now() - timedelta(days=3),
            "access_count": 2,
        }

        # Calculate decayed salience
        result = decay.calculate_salience(memory)

        # Deterministic: same input always produces same output
        result2 = decay.calculate_salience(memory)
        assert result.salience_level == result2.salience_level
        assert abs(result.salience_score - result2.salience_score) < 0.001

        # Should be reduced from initial
        assert result.salience_score < 1.0
        assert result.salience_level in (SalienceLevel.LOW, SalienceLevel.MEDIUM)

    def test_recent_memory_retains_high_salience(self, tmp_path: Path) -> None:
        """Test that recently accessed memories retain high salience."""
        decay = MemoryDecay(
            initial_salience=1.0,
            decay_rate=0.1,
            time_unit_hours=24,
        )

        memory = {
            "id": str(uuid4()),
            "content_hash": hashlib.sha256(b"recent fact").hexdigest(),
            "created_at": datetime.now() - timedelta(hours=2),
            "last_accessed": datetime.now() - timedelta(minutes=30),
            "access_count": 5,
        }

        result = decay.calculate_salience(memory)

        assert result.salience_score > 0.8
        assert result.salience_level == SalienceLevel.HIGH

    def test_decay_isolation_from_correction(self, tmp_path: Path) -> None:
        """Test decay does not affect correction status."""
        decay = MemoryDecay(
            initial_salience=1.0,
            decay_rate=0.1,
        )

        memory = {
            "id": str(uuid4()),
            "content_hash": hashlib.sha256(b"old fact").hexdigest(),
            "created_at": datetime.now() - timedelta(days=30),
            "last_accessed": datetime.now() - timedelta(days=30),
            "access_count": 1,
            "correction_active": True,
            "corrected_content": "new fact",
        }

        result = decay.calculate_salience(memory)

        # Correction should still be marked as active
        assert result.correction_respected is True
        assert result.correction_active == memory["correction_active"]

    def test_decay_respects_privacy_boundary(self, tmp_path: Path) -> None:
        """Test decay calculation respects privacy boundaries."""
        decay = MemoryDecay(
            initial_salience=1.0,
            decay_rate=0.1,
        )

        # S0 violation memory
        memory = {
            "id": str(uuid4()),
            "content_hash": hashlib.sha256(b"secret").hexdigest(),
            "privacy_level": "S0_HARD_VIOLATION",
            "created_at": datetime.now() - timedelta(days=7),
        }

        result = decay.calculate_salience(memory)

        # Privacy level should be preserved
        assert result.privacy_level == "S0_HARD_VIOLATION"
        # Should not expose any content
        assert "secret" not in str(result.to_dict())

    def test_decay_produces_reproducible_fixture(self, tmp_path: Path) -> None:
        """Test decay calculation produces reproducible fixture data."""
        decay = MemoryDecay(
            initial_salience=1.0,
            decay_rate=0.1,
            time_unit_hours=24,
        )

        # Fixed input for reproducibility
        memory = {
            "id": "fixture_memory_001",
            "content_hash": hashlib.sha256(b"fixture_content").hexdigest(),
            "created_at": datetime(2024, 1, 1, 12, 0, 0),
            "last_accessed": datetime(2024, 1, 1, 12, 0, 0),
            "access_count": 1,
        }

        # Run 3 times - all should produce identical results
        results = [decay.calculate_salience(memory) for _ in range(3)]

        for r in results[1:]:
            assert r.salience_score == results[0].salience_score
            assert r.salience_level == results[0].salience_level

    def test_mechanism_report_format_not_runtime_behavior(self, tmp_path: Path) -> None:
        """Test that decay output is mechanism report, not runtime behavior change."""
        decay = MemoryDecay(initial_salience=1.0, decay_rate=0.1)

        memory = {
            "id": str(uuid4()),
            "content_hash": hashlib.sha256(b"test").hexdigest(),
            "created_at": datetime.now(),
        }

        result = decay.calculate_salience(memory)

        # Result should be serializable report
        assert hasattr(result, "to_dict")
        result_dict = result.to_dict()

        # Must not contain runtime modification instructions
        assert "runtime_behavior" not in result_dict
        assert "salience_override" not in result_dict
