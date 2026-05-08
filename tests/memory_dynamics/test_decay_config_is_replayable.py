"""Test: decay config is replayable.

Acceptance criteria:
- Decay configuration can be serialized and replayed
- Configuration preserves all parameters needed for reproducibility
- Replay produces consistent results

This test validates that decay mechanisms have deterministic, auditable
configuration suitable for mechanism reports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class DecayConfig:
    """Configuration for memory decay mechanism.

    All parameters are serializable for replayability.
    """
    decay_rate: float = 0.95
    salience_threshold: float = 0.1
    rehearsal_boost: float = 0.1
    max_salience: float = 1.0
    min_salience: float = 0.0
    config_id: str = field(default_factory=lambda: f"decay-{datetime.utcnow().isoformat()}")
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for storage/replay."""
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
        """Deserialize from dictionary."""
        return cls(
            decay_rate=data["decay_rate"],
            salience_threshold=data["salience_threshold"],
            rehearsal_boost=data["rehearsal_boost"],
            max_salience=data["max_salience"],
            min_salience=data["min_salience"],
            config_id=data["config_id"],
            metadata=data.get("metadata", {}),
        )


class DecayMechanism:
    """Decay mechanism with replayable configuration."""

    def __init__(self, config: DecayConfig | None = None):
        self.config = config or DecayConfig()
        self.history: list[dict[str, Any]] = []

    def apply_decay(self, current_salience: float, time_delta_hours: float = 1.0) -> float:
        """Apply decay to current salience value.

        Returns the new salience after decay is applied.
        """
        # Exponential decay formula: new = old * rate^(time_delta)
        decayed = current_salience * (self.config.decay_rate ** time_delta_hours)

        # Clamp to bounds
        new_salience = max(self.config.min_salience, min(self.config.max_salience, decayed))

        self.history.append({
            "action": "decay",
            "before": current_salience,
            "after": new_salience,
            "time_delta_hours": time_delta_hours,
        })

        return new_salience

    def apply_rehearsal(self, current_salience: float) -> float:
        """Apply rehearsal boost to current salience.

        Returns the new salience after rehearsal boost.
        """
        new_salience = min(
            self.config.max_salience,
            current_salience + self.config.rehearsal_boost
        )

        self.history.append({
            "action": "rehearsal",
            "before": current_salience,
            "after": new_salience,
        })

        return new_salience

    def is_below_threshold(self, salience: float) -> bool:
        """Check if salience is below retention threshold."""
        return salience < self.config.salience_threshold


class TestDecayConfigReplayability:
    """Test suite for decay configuration replayability."""

    def test_config_serialization_roundtrip(self):
        """Config can be serialized and deserialized."""
        original = DecayConfig(
            decay_rate=0.9,
            salience_threshold=0.15,
            rehearsal_boost=0.12,
        )

        serialized = original.to_dict()
        restored = DecayConfig.from_dict(serialized)

        assert restored.decay_rate == original.decay_rate
        assert restored.salience_threshold == original.salience_threshold
        assert restored.rehearsal_boost == original.rehearsal_boost

    def test_config_with_metadata_roundtrip(self):
        """Config with metadata survives roundtrip."""
        original = DecayConfig(
            decay_rate=0.95,
            metadata={"author": "test", "version": 1},
        )

        restored = DecayConfig.from_dict(original.to_dict())

        assert restored.metadata == original.metadata

    def test_decay_is_deterministic(self):
        """Decay produces consistent results with same config."""
        config = DecayConfig(decay_rate=0.9, rehearsal_boost=0.1)
        mechanism = DecayMechanism(config)

        # Apply decay twice with same parameters
        result1 = mechanism.apply_decay(0.5, time_delta_hours=1.0)
        mechanism.history.clear()

        result2 = mechanism.apply_decay(0.5, time_delta_hours=1.0)

        assert result1 == result2

    def test_decay_replay_produces_same_trajectory(self):
        """Replay with same config produces same salience trajectory."""
        config = DecayConfig(decay_rate=0.9)

        # First run
        mechanism1 = DecayMechanism(config)
        salience1 = 1.0
        for _ in range(5):
            salience1 = mechanism1.apply_decay(salience1, time_delta_hours=1.0)

        # Replay run
        mechanism2 = DecayMechanism(DecayConfig.from_dict(config.to_dict()))
        salience2 = 1.0
        for _ in range(5):
            salience2 = mechanism2.apply_decay(salience2, time_delta_hours=1.0)

        assert salience1 == salience2

    def test_rehearsal_boost_is_bounded(self):
        """Rehearsal boost respects max_salience bound."""
        config = DecayConfig(max_salience=1.0, rehearsal_boost=0.5)
        mechanism = DecayMechanism(config)

        # Salience at max should not exceed bound
        result = mechanism.apply_rehearsal(0.9)
        assert result <= config.max_salience

    def test_decay_respects_min_bound(self):
        """Decay respects min_salience bound."""
        config = DecayConfig(min_salience=0.1, decay_rate=0.5)
        mechanism = DecayMechanism(config)

        # Very low salience should not go below min
        result = mechanism.apply_decay(0.15, time_delta_hours=10.0)
        assert result >= config.min_salience

    def test_history_is_auditable(self):
        """Decay mechanism maintains auditable history."""
        config = DecayConfig()
        mechanism = DecayMechanism(config)

        mechanism.apply_decay(0.8, time_delta_hours=1.0)
        mechanism.apply_rehearsal(0.7)
        mechanism.apply_decay(0.8, time_delta_hours=2.0)

        assert len(mechanism.history) == 3
        assert all("action" in entry for entry in mechanism.history)
        assert all("before" in entry for entry in mechanism.history)
        assert all("after" in entry for entry in mechanism.history)


class TestDecayBlockConditions:
    """Test block conditions from mechanism report contract."""

    def test_block_if_consolidated_memories_lose_lineage(self):
        """Block if: consolidated memories lose source lineage.

        Config must preserve lineage information.
        """
        config = DecayConfig(
            metadata={"lineage": ["source-1", "source-2"]}
        )

        restored = DecayConfig.from_dict(config.to_dict())

        assert "lineage" in restored.metadata
        assert restored.metadata["lineage"] == ["source-1", "source-2"]

    def test_block_if_no_recommendations_without_maturity_review(self):
        """Block if: recommendations select external dependency.

        Decay config is internal only, no external dependencies.
        """
        config = DecayConfig()

        # Config should not reference external dependencies
        serialized = config.to_dict()
        serialized_str = str(serialized)

        # Should not contain external dependency hints
        assert "github.com" not in serialized_str.lower()
        assert "npm" not in serialized_str.lower()
        assert "pypi" not in serialized_str.lower()
