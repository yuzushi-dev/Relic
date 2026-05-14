"""Memory reinforcement mechanism.

This module implements reinforcement (rehearsal) that can increase salience
while respecting correction and privacy blocks.
"""

from __future__ import annotations

from typing import Any

from relic.memory_dynamics.types import DecayConfig


class MemoryReinforcement:
    """Memory reinforcement (rehearsal) mechanism.
    
    Reinforcement can increase salience but MUST NOT clear correction
    or privacy blocks.
    """

    def __init__(self, config: DecayConfig | None = None):
        self._config = config or DecayConfig(
            rehearsal_boost=0.1,
            max_salience=1.0,
        )
        self._history: list[dict[str, Any]] = []

    @property
    def config(self) -> DecayConfig:
        """Get the reinforcement configuration."""
        return self._config

    def apply_rehearsal(
        self,
        current_salience: float,
        memory: dict[str, Any] | None = None,
    ) -> float:
        """Apply rehearsal boost to current salience.

        Returns the new salience after rehearsal boost.
        Reinforcement respects correction and privacy blocks.
        """
        new_salience = min(
            self._config.max_salience,
            current_salience + self._config.rehearsal_boost
        )

        record = {
            "action": "rehearsal",
            "before": current_salience,
            "after": new_salience,
        }
        
        # Record correction status if provided
        if memory:
            record["has_correction_block"] = memory.get("correction_active", False)
            record["has_privacy_block"] = memory.get("privacy_level") in (
                "S0_HARD_VIOLATION", "S0", "S0_QUARANTINE",
            )
        
        self._history.append(record)
        return new_salience

    def rehearsal(
        self,
        block_id: str,
        memory: dict[str, Any],
        rehearsal_context: dict | None = None,
    ) -> dict:
        """Perform rehearsal on a memory block.

        Returns a mechanism report (not runtime behavior change).
        """
        original_correction = memory.get("correction_active", False)
        original_privacy = memory.get("privacy_level", "SAFE")
        original_salience = memory.get("salience", 0.5)

        # Rehearsal can increase salience
        new_salience = self.apply_rehearsal(original_salience, memory)

        # Rehearsal MUST NOT clear correction or privacy blocks
        correction_preserved = memory.get("correction_active", False) == original_correction
        privacy_preserved = memory.get("privacy_level", "SAFE") == original_privacy

        return {
            "block_id": block_id,
            "salience_before": original_salience,
            "salience_after": new_salience,
            "rehearsal_count": memory.get("rehearsal_count", 0) + 1,
            "correction_block_preserved": correction_preserved,
            "privacy_block_preserved": privacy_preserved,
            "runtime_affected": False,  # Mechanism report only
            "mechanism": "rehearsal",
        }

    def get_history(self) -> list[dict[str, Any]]:
        """Get rehearsal history for auditing."""
        return self._history.copy()

    def clear_history(self) -> None:
        """Clear rehearsal history."""
        self._history.clear()
