"""Tests for eval contract module.

These tests verify that:
- Evaluation is stubbed/blocked from affecting runtime
- Dataset cards are validated
- Runtime state cannot be affected by evaluation
"""

from __future__ import annotations

from relic.lab.dataset_card import DatasetCard
from relic.lab.eval_contract import (
    EvalCommand,
    EvalCommandStatus,
    EvalContract,
    check_eval_safety,
)


class TestEvalContract:
    """Tests for EvalContract."""

    def test_eval_is_blocked_by_default(self) -> None:
        """Verify eval is blocked by default."""
        contract = EvalContract()
        command = contract.validate_eval_request()

        assert command.is_blocked() is True
        assert command.status == EvalCommandStatus.BLOCKED

    def test_eval_blocks_with_dataset_card(self) -> None:
        """Verify eval blocks even with valid dataset_card."""
        card = DatasetCard(
            name="test-eval",
            description="Test evaluation dataset",
            license="MIT",
            privacy_level="public",
            created_at="2024-01-01T00:00:00",
            source="test",
        )

        contract = EvalContract()
        command = contract.validate_eval_request(dataset_card=card)

        assert command.is_blocked() is True
        assert command.dataset_card == card

    def test_eval_dry_run_allowed(self) -> None:
        """Verify dry-run evaluation is allowed."""
        contract = EvalContract()
        command = contract.validate_eval_request(dry_run=True)

        assert command.is_dry_run() is True
        assert command.metrics.get("dry_run") is True
        assert command.metrics.get("runtime_affected") is False

    def test_check_can_eval_returns_dry_run_available(self) -> None:
        """Verify check_can_eval returns dry-run capability."""
        contract = EvalContract()
        can_eval, reason = contract.check_can_eval()

        assert can_eval is True  # Dry-run is available
        assert "dry_run" in reason.lower()

    def test_get_evaluation_report_returns_blocked_status(self) -> None:
        """Verify evaluation report shows blocked status."""
        contract = EvalContract()
        report = contract.get_evaluation_report()

        assert report["status"] == "blocked"
        assert report["runtime_affected"] is False
        assert "available_modes" in report
        assert "dry_run" in report["available_modes"]

    def test_runtime_safe_flag_is_true(self) -> None:
        """Verify EvalContract has runtime_safe=True."""
        contract = EvalContract()
        assert contract.runtime_safe is True

    def test_is_eval_blocked_flag_is_true(self) -> None:
        """Verify EvalContract has is_eval_blocked=True."""
        contract = EvalContract()
        assert contract.is_eval_blocked is True

    def test_eval_contract_metrics_empty(self) -> None:
        """Verify evaluation metrics are empty (eval is blocked)."""
        contract = EvalContract()
        assert len(contract.evaluation_results) == 0


class TestEvalCommandStatus:
    """Tests for EvalCommandStatus enum."""

    def test_blocked_status_exists(self) -> None:
        """Verify BLOCKED status exists."""
        assert EvalCommandStatus.BLOCKED.value == "blocked"

    def test_validated_status_exists(self) -> None:
        """Verify VALIDATED status exists."""
        assert EvalCommandStatus.VALIDATED.value == "validated"

    def test_dry_run_status_exists(self) -> None:
        """Verify DRY_RUN status exists."""
        assert EvalCommandStatus.DRY_RUN.value == "dry_run"

    def test_not_implemented_status_exists(self) -> None:
        """Verify NOT_IMPLEMENTED status exists."""
        assert EvalCommandStatus.NOT_IMPLEMENTED.value == "not_implemented"


class TestCheckEvalSafety:
    """Tests for check_eval_safety function."""

    def test_check_eval_safety_returns_safe(self) -> None:
        """Verify check_eval_safety returns (True, details)."""
        is_safe, details = check_eval_safety()

        assert is_safe is True
        assert "runtime" in details.lower()


class TestEvalCommand:
    """Tests for EvalCommand dataclass."""

    def test_eval_command_blocked_default(self) -> None:
        """Verify EvalCommand is blocked by default."""
        command = EvalCommand()

        assert command.is_blocked() is True
        assert command.status == EvalCommandStatus.BLOCKED

    def test_eval_command_dry_run(self) -> None:
        """Verify EvalCommand with dry_run status."""
        command = EvalCommand(
            status=EvalCommandStatus.DRY_RUN,
            message="Dry run complete",
            metrics={"dry_run": True},
        )

        assert command.is_blocked() is False
        assert command.is_dry_run() is True

    def test_eval_command_message_not_empty(self) -> None:
        """Verify EvalCommand has non-empty default message."""
        command = EvalCommand()
        assert command.message != ""
