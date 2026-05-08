"""Train contract module for adapter training labs.

This module defines the contract for adapter training commands,
ensuring training cannot start or affect runtime without proper validation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from relic.lab.dataset_card import DatasetCard


class TrainCommandStatus(Enum):
    """Status of a training command contract."""

    BLOCKED = "blocked"
    VALIDATED = "validated"
    READY = "ready"
    NOT_IMPLEMENTED = "not_implemented"


@dataclass
class TrainCommand:
    """Represents a training command contract.

    This is a contract-only implementation. The actual training
    functionality is blocked to prevent runtime modifications.

    Attributes:
        status: Current status of the command.
        dataset_card: Required dataset card for training.
        message: Human-readable message about the command.
    """

    status: TrainCommandStatus = TrainCommandStatus.BLOCKED
    dataset_card: DatasetCard | None = None
    message: str = "Training is not available in this environment."

    def is_blocked(self) -> bool:
        """Check if training is blocked."""
        return self.status == TrainCommandStatus.BLOCKED

    def get_blocked_message(self) -> str:
        """Get the blocked message."""
        return (
            "Adapter training is blocked for security and privacy reasons. "
            "Training can only occur in controlled lab environments with proper "
            "dataset validation and approval workflows."
        )


@dataclass
class TrainContract:
    """Contract for adapter training operations.

    This contract ensures:
    - Training commands are blocked by default
    - Dataset cards are validated before any training
    - Runtime state cannot be affected by training operations
    """

    is_training_blocked: bool = True
    validation_required: bool = True
    runtime_safe: bool = True

    def validate_training_request(
        self,
        dataset_card: DatasetCard | None = None,
    ) -> TrainCommand:
        """Validate a training request.

        Args:
            dataset_card: Required dataset card for validation.

        Returns:
            TrainCommand with blocked status and message.
        """
        if dataset_card is None or not dataset_card.is_valid():
            return TrainCommand(
                status=TrainCommandStatus.BLOCKED,
                dataset_card=dataset_card,
                message="Training blocked: invalid or missing dataset_card. "
                        "A valid dataset_card is required for any training operation.",
            )

        command = TrainCommand(
            status=TrainCommandStatus.BLOCKED,
            dataset_card=dataset_card,
            message="Training blocked: adapter training cannot be initiated in this environment.",
        )

        return command

    def check_can_train(self) -> tuple[bool, str]:
        """Check if training can proceed.

        Returns:
            Tuple of (can_train, reason). Always returns (False, reason).
        """
        return (
            False,
            "Adapter training is not available. Training operations are blocked "
            "to prevent runtime modifications."
        )


def check_training_safety() -> tuple[bool, str]:
    """Check if the environment is safe for training.

    This function verifies that training cannot start or affect runtime.

    Returns:
        Tuple of (is_safe, details).
    """
    return (
        True,  # Environment is safe because training is blocked
        "Training is blocked at the contract level. No runtime modifications possible."
    )
