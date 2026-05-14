"""Test: reinforcement increases useful memory.

Acceptance criteria:
- Rehearsal can increase memory salience
- Mechanism report outputs remain mechanism reports
"""

from __future__ import annotations

from relic.memory_dynamics import MemoryDynamicsService, MemoryReinforcement
from relic.persistence import PrivacyLevel


class TestReinforcementIncreasesUsefulMemory:
    """Tests for reinforcement increasing useful memory salience."""

    def test_reinforcement_increases_salience(self) -> None:
        """Reinforcement can increase memory salience."""
        service = MemoryDynamicsService()
        
        # Register memory
        memory = service.register_memory(
            memory_id="test-1",
            content="useful fact",
            salience=0.5,
        )
        
        # Apply reinforcement
        result = service.apply_reinforcement("test-1")
        
        assert result is not None
        assert result["salience_after"] > result["salience_before"]
        assert result["runtime_affected"] is False

    def test_reinforcement_multiple_times_accumulates(self) -> None:
        """Multiple reinforcements increase salience further."""
        service = MemoryDynamicsService()
        
        service.register_memory(
            memory_id="test-2",
            content="fact to rehearse",
            salience=0.3,
        )
        
        for _ in range(3):
            result = service.apply_reinforcement("test-2")
            assert result is not None
        
        memory = service.get_memory("test-2")
        assert memory is not None
        assert memory["salience"] > 0.3

    def test_reinforcement_preserves_correction_block(self) -> None:
        """Reinforcement MUST NOT clear correction blocks."""
        service = MemoryDynamicsService()
        
        service.register_memory(
            memory_id="test-3",
            content="corrected content",
            salience=0.5,
        )
        service.set_correction_active("test-3", True)
        
        result = service.apply_reinforcement("test-3")
        
        assert result is not None
        assert result["correction_block_preserved"] is True

    def test_reinforcement_preserves_privacy_block(self) -> None:
        """Reinforcement MUST NOT clear privacy blocks."""
        service = MemoryDynamicsService()
        
        service.register_memory(
            memory_id="test-4",
            content="private content",
            salience=0.5,
            privacy_level=PrivacyLevel.S1_QUARANTINE,
        )
        
        result = service.apply_reinforcement("test-4")
        
        assert result is not None
        assert result["privacy_block_preserved"] is True

    def test_mechanism_report_not_runtime_behavior(self) -> None:
        """Verify reinforcement returns mechanism report, not runtime change."""
        reinforcement = MemoryReinforcement()
        
        memory = {
            "block_id": "test-5",
            "content": "content",
            "salience": 0.5,
            "correction_active": True,
        }
        
        result = reinforcement.rehearsal("test-5", memory)
        
        assert result["runtime_affected"] is False
        assert "mechanism" in result
        assert result["mechanism"] == "rehearsal"
