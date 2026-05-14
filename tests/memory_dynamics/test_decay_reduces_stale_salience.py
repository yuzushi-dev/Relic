"""Tests for decay reduces stale salience.

Acceptance criteria:
- stale memory salience decays deterministically on fixture
- mechanism report outputs remain mechanism reports
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from relic.memory_dynamics import MemoryDecay, SalienceLevel


class TestDecayReducesStaleSalience:
    """Tests verifying memory decay reduces stale memory salience deterministically."""

    def test_decay_reduces_stale_memory_salience_deterministically(self, tmp_path: Path) -> None:
        """Test that stale memory salience decays deterministically."""
        decay = MemoryDecay(
            initial_salience=1.0,
            decay_rate=0.1,
            time_unit_hours=24,
        )

        memory = {
            "id": str(uuid4()),
            "content_hash": hashlib.sha256(b"old fact").hexdigest(),
            "created_at": datetime.now() - timedelta(days=7),
            "last_accessed": datetime.now() - timedelta(days=3),
            "access_count": 2,
        }

        result = decay.calculate_salience(memory)
        result2 = decay.calculate_salience(memory)

        assert result.salience_level == result2.salience_level
        assert abs(result.salience_score - result2.salience_score) < 0.001
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

        assert result.correction_respected is True
        assert result.correction_active == memory["correction_active"]

    def test_decay_respects_privacy_boundary(self, tmp_path: Path) -> None:
        """Test decay calculation respects privacy boundaries."""
        decay = MemoryDecay(
            initial_salience=1.0,
            decay_rate=0.1,
        )

        memory = {
            "id": str(uuid4()),
            "content_hash": hashlib.sha256(b"secret").hexdigest(),
            "privacy_level": "S0_HARD_VIOLATION",
            "created_at": datetime.now() - timedelta(days=7),
        }

        result = decay.calculate_salience(memory)

        assert result.privacy_level == "S0_HARD_VIOLATION"
        assert "secret" not in str(result.to_dict())

    def test_decay_produces_reproducible_fixture(self, tmp_path: Path) -> None:
        """Test decay calculation produces reproducible fixture data."""
        decay = MemoryDecay(
            initial_salience=1.0,
            decay_rate=0.1,
            time_unit_hours=24,
        )

        memory = {
            "id": "fixture_memory_001",
            "content_hash": hashlib.sha256(b"fixture_content").hexdigest(),
            "created_at": datetime(2024, 1, 1, 12, 0, 0),
            "last_accessed": datetime(2024, 1, 1, 12, 0, 0),
            "access_count": 1,
        }

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
        result_dict = result.to_dict()

        assert "runtime_behavior" not in result_dict
        assert "salience_override" not in result_dict
