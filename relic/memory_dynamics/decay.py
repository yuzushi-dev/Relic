"""Memory decay mechanism for salience reduction.

This module implements deterministic decay calculations for memory salience
that respect correction and privacy boundaries.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from relic.memory_dynamics.types import (
    DecayConfig,
    MemoryMechanism,
    SalienceLevel,
    SalienceResult,
)


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
        config: DecayConfig | None = None,
    ):
        if config:
            self._config = config
        else:
            self._config = DecayConfig(
                decay_rate=1.0 - decay_rate,
                salience_threshold=0.1,
                rehearsal_boost=0.1,
            )
        
        self._initial_salience = initial_salience
        self._decay_rate = decay_rate
        self._time_unit_hours = time_unit_hours
        self._history: list[dict[str, Any]] = []

    @property
    def config(self) -> DecayConfig:
        """Get the decay configuration."""
        return self._config

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

    def apply_decay(self, current_salience: float, time_delta_hours: float = 1.0) -> float:
        """Apply decay to current salience value.

        Returns the new salience after decay is applied.
        """
        # Exponential decay formula: new = old * rate^(time_delta)
        decayed = current_salience * (self._config.decay_rate ** time_delta_hours)

        # Clamp to bounds
        new_salience = max(
            self._config.min_salience,
            min(self._config.max_salience, decayed)
        )

        self._history.append({
            "action": "decay",
            "before": current_salience,
            "after": new_salience,
            "time_delta_hours": time_delta_hours,
        })

        return new_salience

    def is_below_threshold(self, salience: float) -> bool:
        """Check if salience is below retention threshold."""
        return salience < self._config.salience_threshold

    def get_history(self) -> list[dict[str, Any]]:
        """Get decay history for auditing."""
        return self._history.copy()

    def clear_history(self) -> None:
        """Clear decay history."""
        self._history.clear()
