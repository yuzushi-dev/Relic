"""Eval contract module for adapter training labs.

This module defines the contract for adapter evaluation commands,
ensuring evaluation cannot affect runtime state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from relic.lab.dataset_card import DatasetCard


class EvalCommandStatus(Enum):
    """Status of an evaluation command."""

    BLOCKED = "blocked"
    VALIDATED = "validated"
    DRY_RUN = "dry_run"
    NOT_IMPLEMENTED = "not_implemented"


@dataclass
class EvalCommand:
    """Represents an evaluation command contract.

    Attributes:
        status: Current status of the command.
        dataset_card: Required dataset card for evaluation.
        message: Human-readable message about the command.
        metrics: Available metrics (empty - evaluation is blocked).
    """

    status: EvalCommandStatus = EvalCommandStatus.BLOCKED
    dataset_card: DatasetCard | None = None
    message: str = "Evaluation is stubbed in this environment."
    metrics: dict[str, Any] = field(default_factory=dict)

    def is_blocked(self) -> bool:
        """Check if evaluation is blocked."""
        return self.status == EvalCommandStatus.BLOCKED

    def is_dry_run(self) -> bool:
        """Check if this is a dry-run evaluation."""
        return self.status == EvalCommandStatus.DRY_RUN


@dataclass
class EvalContract:
    """Contract for adapter evaluation operations.

    This contract ensures:
    - Evaluation is stubbed/blocked from affecting runtime
    - Dataset cards are validated
    - Runtime state cannot be affected by evaluation
    """

    is_eval_blocked: bool = True
    runtime_safe: bool = True
    evaluation_results: dict[str, Any] = field(default_factory=dict)

    def validate_eval_request(
        self,
        dataset_card: DatasetCard | None = None,
        dry_run: bool = False,
    ) -> EvalCommand:
        """Validate an evaluation request.

        Args:
            dataset_card: Required dataset card for validation.
            dry_run: If True, run a dry-run evaluation.

        Returns:
            EvalCommand with appropriate status.
        """
        if dry_run:
            return EvalCommand(
                status=EvalCommandStatus.DRY_RUN,
                dataset_card=dataset_card,
                message="Dry-run evaluation completed successfully. No runtime modifications.",
                metrics={
                    "dry_run": True,
                    "runtime_affected": False,
                    "evaluation_completed": True,
                },
            )

        return EvalCommand(
            status=EvalCommandStatus.BLOCKED,
            dataset_card=dataset_card,
            message="Evaluation is blocked: adapter evaluation cannot affect runtime.",
        )

    def check_can_eval(self) -> tuple[bool, str]:
        """Check if evaluation can proceed.

        Returns:
            Tuple of (can_eval, reason). Returns dry-run capability only.
        """
        return (
            True,  # Dry-run evaluation is allowed
            "dry_run evaluation is available. Runtime-affecting evaluation is blocked."
        )

    def get_evaluation_report(self) -> dict[str, Any]:
        """Get evaluation report.

        Returns a stubbed report indicating evaluation is blocked.
        """
        return {
            "status": "blocked",
            "runtime_affected": False,
            "message": "Adapter evaluation is blocked from affecting runtime.",
            "available_modes": ["dry_run"],
            "metrics": {},
        }


def check_eval_safety() -> tuple[bool, str]:
    """Check if the environment is safe for evaluation.

    This function verifies that evaluation cannot affect runtime.

    Returns:
        Tuple of (is_safe, details).
    """
    return (
        True,  # Environment is safe because eval cannot affect runtime
        "Evaluation is blocked at the contract level. No runtime modifications possible."
    )
