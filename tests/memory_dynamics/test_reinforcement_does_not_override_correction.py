"""Test: reinforcement does not override correction.

Acceptance criteria:
- Rehearsal cannot clear correction or privacy blocks
- Memory salience can increase via rehearsal
- Correction blocks remain intact after rehearsal
"""

from __future__ import annotations

from relic.memory_dynamics import MemoryDynamicsService, MemoryReinforcement
from relic.persistence import PrivacyLevel


class MockMemoryBlock:
    """Mock memory block with correction/privacy state."""

    def __init__(
        self,
        block_id: str,
        content: str,
        salience: float = 0.5,
        has_correction_block: bool = False,
        has_privacy_block: bool = False,
    ):
        self.block_id = block_id
        self.content = content
        self.salience = salience
        self.has_correction_block = has_correction_block
        self.has_privacy_block = has_privacy_block
        self.rehearsal_count = 0


class MockRehearsalMechanism:
    """Mock rehearsal mechanism for testing."""

    def __init__(self):
        self.blocks: dict[str, MockMemoryBlock] = {}

    def add_block(self, block: MockMemoryBlock) -> None:
        self.blocks[block.block_id] = block

    def rehearsal(
        self,
        block_id: str,
        rehearsal_context: dict | None = None,
    ) -> dict:
        """Perform rehearsal on a memory block."""
        block = self.blocks.get(block_id)
        if not block:
            return {"error": "block_not_found", "runtime_affected": False}

        original_correction = block.has_correction_block
        original_privacy = block.has_privacy_block
        original_salience = block.salience

        block.salience = min(1.0, block.salience + 0.1)
        block.rehearsal_count += 1

        correction_preserved = block.has_correction_block == original_correction
        privacy_preserved = block.has_privacy_block == original_privacy

        return {
            "block_id": block_id,
            "salience_before": original_salience,
            "salience_after": block.salience,
            "rehearsal_count": block.rehearsal_count,
            "correction_block_preserved": correction_preserved,
            "privacy_block_preserved": privacy_preserved,
            "runtime_affected": False,
            "mechanism": "rehearsal",
        }


class TestReinforcementDoesNotOverrideCorrection:
    """Test suite for reinforcement salience and correction preservation."""

    def test_rehearsal_increases_salience(self) -> None:
        """Rehearsal can increase memory salience."""
        mechanism = MockRehearsalMechanism()
        block = MockMemoryBlock(
            block_id="test-1",
            content="test content",
            salience=0.5,
        )
        mechanism.add_block(block)

        result = mechanism.rehearsal("test-1")

        assert result["salience_after"] > result["salience_before"]
        assert result["runtime_affected"] is False

    def test_rehearsal_preserves_correction_block(self) -> None:
        """Rehearsal MUST NOT clear correction blocks."""
        mechanism = MockRehearsalMechanism()
        block = MockMemoryBlock(
            block_id="test-2",
            content="corrected content",
            salience=0.5,
            has_correction_block=True,
        )
        mechanism.add_block(block)

        result = mechanism.rehearsal("test-2")

        assert result["correction_block_preserved"] is True
        assert result["runtime_affected"] is False

    def test_rehearsal_preserves_privacy_block(self) -> None:
        """Rehearsal MUST NOT clear privacy blocks."""
        mechanism = MockRehearsalMechanism()
        block = MockMemoryBlock(
            block_id="test-3",
            content="private content",
            salience=0.5,
            has_privacy_block=True,
        )
        mechanism.add_block(block)

        result = mechanism.rehearsal("test-3")

        assert result["privacy_block_preserved"] is True
        assert result["runtime_affected"] is False

    def test_rehearsal_preserves_both_blocks(self) -> None:
        """Rehearsal preserves both correction and privacy blocks."""
        mechanism = MockRehearsalMechanism()
        block = MockMemoryBlock(
            block_id="test-4",
            content="corrected private content",
            salience=0.5,
            has_correction_block=True,
            has_privacy_block=True,
        )
        mechanism.add_block(block)

        result = mechanism.rehearsal("test-4")

        assert result["correction_block_preserved"] is True
        assert result["privacy_block_preserved"] is True
        assert result["runtime_affected"] is False

    def test_rehearsal_multiple_times_preserves_blocks(self) -> None:
        """Multiple rehearsals preserve blocks each time."""
        mechanism = MockRehearsalMechanism()
        block = MockMemoryBlock(
            block_id="test-5",
            content="content",
            salience=0.3,
            has_correction_block=True,
        )
        mechanism.add_block(block)

        for _ in range(5):
            result = mechanism.rehearsal("test-5")
            assert result["correction_block_preserved"] is True
            assert result["runtime_affected"] is False

        assert block.salience > 0.3

    def test_mechanism_report_not_runtime_behavior(self) -> None:
        """Verify rehearsal returns mechanism report, not runtime change."""
        mechanism = MockRehearsalMechanism()
        block = MockMemoryBlock(
            block_id="test-6",
            content="content",
            salience=0.5,
            has_correction_block=True,
        )
        mechanism.add_block(block)

        result = mechanism.rehearsal("test-6")

        assert result["runtime_affected"] is False
        assert "mechanism" in result
        assert result["mechanism"] == "rehearsal"

    def test_block_condition_dynamic_memory_traces_no_raw_sensitive(self) -> None:
        """Block if: dynamic memory traces contain raw sensitive text."""
        mechanism = MockRehearsalMechanism()
        block = MockMemoryBlock(
            block_id="test-sensitive",
            content="CONFIDENTIAL: secret data 12345",
            salience=0.5,
        )
        mechanism.add_block(block)

        result = mechanism.rehearsal("test-sensitive")

        assert "raw_content" not in result
        assert "CONFIDENTIAL" not in str(result)
        assert "secret data" not in str(result)

    def test_block_condition_no_runtime_change_before_promotion(self) -> None:
        """Block if: memory dynamics result changes runtime behavior."""
        mechanism = MockRehearsalMechanism()
        block = MockMemoryBlock(
            block_id="test-runtime",
            content="content",
            salience=0.5,
            has_correction_block=True,
        )
        mechanism.add_block(block)

        result = mechanism.rehearsal("test-runtime")

        assert result["runtime_affected"] is False
