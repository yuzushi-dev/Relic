"""Tests for train contract module.

These tests verify that:
- Training is blocked by default
- Dataset cards are validated before training
- Runtime state cannot be affected by training
"""

from __future__ import annotations

from relic.lab.dataset_card import DatasetCard
from relic.lab.train_contract import (
    TrainCommand,
    TrainCommandStatus,
    TrainContract,
    check_training_safety,
)


class TestTrainContract:
    """Tests for TrainContract."""

    def test_train_is_blocked_by_default(self) -> None:
        """Verify training is blocked by default."""
        contract = TrainContract()
        command = contract.validate_training_request()

        assert command.is_blocked() is True
        assert command.status == TrainCommandStatus.BLOCKED

    def test_train_blocks_with_dataset_card(self) -> None:
        """Verify training blocks even with valid dataset_card."""
        card = DatasetCard(
            name="test-train",
            description="Test training dataset",
            license="MIT",
            privacy_level="public",
            created_at="2024-01-01T00:00:00",
            source="test",
        )

        contract = TrainContract()
        command = contract.validate_training_request(dataset_card=card)

        assert command.is_blocked() is True
        assert command.dataset_card == card

    def test_train_blocks_with_invalid_dataset_card(self) -> None:
        """Verify training blocks when dataset_card is absent."""
        contract = TrainContract()
        command = contract.validate_training_request(dataset_card=None)

        assert command.is_blocked() is True
        assert "invalid" in command.message.lower() or "missing" in command.message.lower()

    def test_check_can_train_returns_false(self) -> None:
        """Verify check_can_train returns (False, reason)."""
        contract = TrainContract()
        can_train, reason = contract.check_can_train()

        assert can_train is False
        assert "blocked" in reason.lower() or "not available" in reason.lower()

    def test_runtime_safe_flag_is_true(self) -> None:
        """Verify TrainContract has runtime_safe=True."""
        contract = TrainContract()
        assert contract.runtime_safe is True

    def test_validation_required_flag_is_true(self) -> None:
        """Verify TrainContract has validation_required=True."""
        contract = TrainContract()
        assert contract.validation_required is True

    def test_is_training_blocked_flag_is_true(self) -> None:
        """Verify TrainContract has is_training_blocked=True."""
        contract = TrainContract()
        assert contract.is_training_blocked is True


class TestTrainCommandStatus:
    """Tests for TrainCommandStatus enum."""

    def test_blocked_status_exists(self) -> None:
        """Verify BLOCKED status exists."""
        assert TrainCommandStatus.BLOCKED.value == "blocked"

    def test_validated_status_exists(self) -> None:
        """Verify VALIDATED status exists."""
        assert TrainCommandStatus.VALIDATED.value == "validated"

    def test_ready_status_exists(self) -> None:
        """Verify READY status exists."""
        assert TrainCommandStatus.READY.value == "ready"

    def test_not_implemented_status_exists(self) -> None:
        """Verify NOT_IMPLEMENTED status exists."""
        assert TrainCommandStatus.NOT_IMPLEMENTED.value == "not_implemented"


class TestCheckTrainingSafety:
    """Tests for check_training_safety function."""

    def test_check_training_safety_returns_safe(self) -> None:
        """Verify check_training_safety returns (True, details)."""
        is_safe, details = check_training_safety()

        assert is_safe is True
        assert "blocked" in details.lower() or "training" in details.lower()


class TestTrainCommand:
    """Tests for TrainCommand dataclass."""

    def test_train_command_blocked_default(self) -> None:
        """Verify TrainCommand is blocked by default."""
        command = TrainCommand()

        assert command.is_blocked() is True
        assert command.status == TrainCommandStatus.BLOCKED

    def test_train_command_message_not_empty(self) -> None:
        """Verify TrainCommand has non-empty default message."""
        command = TrainCommand()
        assert command.message != ""

    def test_get_blocked_message(self) -> None:
        """Verify get_blocked_message returns non-empty message."""
        command = TrainCommand()
        blocked_msg = command.get_blocked_message()

        assert blocked_msg != ""
        assert "blocked" in blocked_msg.lower()
