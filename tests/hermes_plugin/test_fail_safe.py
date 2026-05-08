"""Tests for fail-safe mechanisms.

These tests verify:
- Fail-safe triggers correctly block guidance
- Fail-safe is fail-closed
- Events are recorded for audit
"""

from __future__ import annotations

from relic.hermes_plugin.fail_safe import (
    FailSafeRegistry,
    FailSafeTrigger,
    create_fail_safe_blocked_result,
    create_fail_safe_disabled_result,
)


class TestFailSafeRegistry:
    """Test fail-safe registry functionality."""

    def test_registry_starts_not_triggered(self) -> None:
        """Registry should start in non-triggered state."""
        registry = FailSafeRegistry(enabled=True)
        assert registry.is_triggered is False
        assert registry.enabled is True

    def test_registry_starts_disabled(self) -> None:
        """Registry can start in disabled state."""
        registry = FailSafeRegistry(enabled=False)
        assert registry.enabled is False
        assert registry.is_triggered is False

    def test_trigger_records_event(self) -> None:
        """Trigger should record an event."""
        registry = FailSafeRegistry(enabled=True)
        result = registry.trigger(
            reason="test_reason",
            trigger=FailSafeTrigger.HOOK_ERROR,
        )
        assert result.triggered is True
        assert result.blocked is True
        assert result.trigger_reason == "test_reason"
        assert len(registry.get_events()) == 1

    def test_trigger_calls_callbacks(self) -> None:
        """Trigger should call registered callbacks."""
        registry = FailSafeRegistry(enabled=True)
        callback_called = []
        registry.register_callback(lambda r: callback_called.append(r))
        registry.trigger(reason="test")
        assert len(callback_called) == 1
        assert callback_called[0] == "test"

    def test_callback_exception_does_not_propagate(self) -> None:
        """Callback exception should not propagate."""
        registry = FailSafeRegistry(enabled=True)
        registry.register_callback(lambda r: 1 / 0)
        # Should not raise
        registry.trigger(reason="test")

    def test_check_returns_not_triggered_when_disabled(self) -> None:
        """Check should return not triggered when disabled."""
        registry = FailSafeRegistry(enabled=False)
        result = registry.check()
        assert result.triggered is False
        assert result.blocked is False

    def test_check_returns_triggered_after_trigger(self) -> None:
        """Check should return triggered after trigger."""
        registry = FailSafeRegistry(enabled=True)
        registry.trigger(reason="test")
        result = registry.check()
        assert result.triggered is True
        assert result.blocked is True

    def test_reset_clears_triggered_state(self) -> None:
        """Reset should clear triggered state."""
        registry = FailSafeRegistry(enabled=True)
        registry.trigger(reason="test")
        assert registry.is_triggered is True
        registry.reset()
        assert registry.is_triggered is False
        # Events should still be present for audit
        assert len(registry.get_events()) == 1

    def test_get_last_trigger_reason(self) -> None:
        """Should return last trigger reason."""
        registry = FailSafeRegistry(enabled=True)
        registry.trigger(reason="first")
        registry.trigger(reason="second")
        assert registry.get_last_trigger_reason() == "second"

    def test_get_last_trigger_reason_when_empty(self) -> None:
        """Should return None when no triggers."""
        registry = FailSafeRegistry(enabled=True)
        assert registry.get_last_trigger_reason() is None


class TestFailSafeResult:
    """Test fail-safe result factory functions."""

    def test_create_disabled_result(self) -> None:
        """Factory should create disabled result."""
        result = create_fail_safe_disabled_result()
        assert result.triggered is False
        assert result.blocked is False
        assert result.trigger_reason is None

    def test_create_blocked_result(self) -> None:
        """Factory should create blocked result."""
        result = create_fail_safe_blocked_result("test reason")
        assert result.triggered is True
        assert result.blocked is True
        assert result.trigger_reason == "test reason"


class TestFailSafeAuditTrail:
    """Test fail-safe audit trail."""

    def test_events_preserve_trigger_type(self) -> None:
        """Events should preserve trigger type."""
        registry = FailSafeRegistry(enabled=True)
        registry.trigger(
            reason="test",
            trigger=FailSafeTrigger.SECURITY_VIOLATION,
        )
        events = registry.get_events()
        assert len(events) == 1
        assert events[0].trigger == FailSafeTrigger.SECURITY_VIOLATION

    def test_events_preserve_trace_id(self) -> None:
        """Events should preserve trace ID."""
        registry = FailSafeRegistry(enabled=True)
        registry.trigger(
            reason="test",
            trace_id="trace-123",
        )
        events = registry.get_events()
        assert events[0].trace_id == "trace-123"

    def test_events_preserve_metadata(self) -> None:
        """Events should preserve metadata."""
        registry = FailSafeRegistry(enabled=True)
        registry.trigger(
            reason="test",
            metadata={"key": "value"},
        )
        events = registry.get_events()
        assert events[0].metadata == {"key": "value"}

    def test_clear_events(self) -> None:
        """Should clear events for testing."""
        registry = FailSafeRegistry(enabled=True)
        registry.trigger(reason="test")
        assert len(registry.get_events()) == 1
        registry.clear_events()
        assert len(registry.get_events()) == 0
