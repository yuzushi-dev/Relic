"""Tests for promote command blocking.

These tests verify that:
- Promote command is stubbed and blocked
- Runtime state cannot be affected by promotion
- Blocked operations are properly reported
"""

from __future__ import annotations

from relic.lab.promote_blocked import (
    PromoteBlocked,
    PromoteCommandStatus,
    PromoteResult,
    generate_blocked_report,
)


class TestPromoteBlocked:
    """Tests for PromoteBlocked contract."""

    def test_promote_is_blocked(self) -> None:
        """Verify promote operation is blocked."""
        blocker = PromoteBlocked()
        result = blocker.promote(adapter_id="test-adapter")

        assert result.can_promote is False
        assert result.status == PromoteCommandStatus.BLOCKED

    def test_promote_blocks_with_adapter_id(self) -> None:
        """Verify promote blocks even with adapter_id provided."""
        blocker = PromoteBlocked()
        result = blocker.promote(adapter_id="my-adapter-v1")

        assert result.can_promote is False
        assert result.details.get("adapter_id") == "my-adapter-v1"
        assert result.details.get("runtime_affected") is False

    def test_promote_blocks_with_target_env(self) -> None:
        """Verify promote blocks even with target_env provided."""
        blocker = PromoteBlocked()
        result = blocker.promote(target_env="production")

        assert result.can_promote is False
        assert result.details.get("target_env") == "production"
        assert result.details.get("runtime_affected") is False

    def test_promote_blocks_with_all_params(self) -> None:
        """Verify promote blocks with all parameters."""
        blocker = PromoteBlocked()
        result = blocker.promote(
            adapter_id="test-adapter",
            target_env="staging",
        )

        assert result.can_promote is False
        assert result.status == PromoteCommandStatus.BLOCKED
        assert "blocked" in result.message.lower()

    def test_check_can_promote_returns_false(self) -> None:
        """Verify check_can_promote returns (False, reason)."""
        blocker = PromoteBlocked()
        can_promote, reason = blocker.check_can_promote()

        assert can_promote is False
        assert "blocked" in reason.lower()

    def test_get_blocked_report_returns_proper_structure(self) -> None:
        """Verify get_blocked_report returns proper report structure."""
        blocker = PromoteBlocked()
        report = blocker.get_blocked_report()

        assert report["status"] == "blocked"
        assert report["can_promote"] is False
        assert report["runtime_affected"] is False
        assert "blocked_operations" in report["details"]
        assert "promote" in report["details"]["blocked_operations"]

    def test_promote_result_to_dict(self) -> None:
        """Verify PromoteResult.to_dict returns proper structure."""
        result = PromoteResult(
            status=PromoteCommandStatus.BLOCKED,
            can_promote=False,
            message="Test blocked message",
            details={"key": "value"},
        )

        data = result.to_dict()
        assert data["status"] == "blocked"
        assert data["can_promote"] is False
        assert data["message"] == "Test blocked message"
        assert data["details"]["key"] == "value"

    def test_generate_blocked_report(self) -> None:
        """Verify generate_blocked_report helper function."""
        result = generate_blocked_report(
            adapter_id="helper-test",
            target_env="prod",
        )

        assert result.can_promote is False
        assert result.status == PromoteCommandStatus.BLOCKED
        assert result.details.get("adapter_id") == "helper-test"
        assert result.details.get("target_env") == "prod"

    def test_generate_blocked_report_no_params(self) -> None:
        """Verify generate_blocked_report with no parameters."""
        result = generate_blocked_report()

        assert result.can_promote is False
        assert result.status == PromoteCommandStatus.BLOCKED
        assert result.details.get("adapter_id") is None
        assert result.details.get("target_env") is None

    def test_runtime_safe_flag_is_true(self) -> None:
        """Verify PromoteBlocked has runtime_safe=True."""
        blocker = PromoteBlocked()
        assert blocker.runtime_safe is True

    def test_is_promote_blocked_flag_is_true(self) -> None:
        """Verify PromoteBlocked has is_promote_blocked=True."""
        blocker = PromoteBlocked()
        assert blocker.is_promote_blocked is True

    def test_blocked_message_mentions_runtime(self) -> None:
        """Verify blocked message mentions runtime protection."""
        blocker = PromoteBlocked()
        result = blocker.promote()

        # Message should mention security or runtime
        assert "runtime" in result.message.lower() or "security" in result.message.lower()


class TestPromoteCommandStatus:
    """Tests for PromoteCommandStatus enum."""

    def test_blocked_status_exists(self) -> None:
        """Verify BLOCKED status exists."""
        assert PromoteCommandStatus.BLOCKED.value == "blocked"

    def test_stubbed_status_exists(self) -> None:
        """Verify STUBBED status exists."""
        assert PromoteCommandStatus.STUBBED.value == "stubbed"

    def test_not_implemented_status_exists(self) -> None:
        """Verify NOT_IMPLEMENTED status exists."""
        assert PromoteCommandStatus.NOT_IMPLEMENTED.value == "not_implemented"
