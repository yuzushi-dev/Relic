"""Tests for pre_tool_call enforcement.

These tests verify:
- pre_tool_call enforces TOOL_PERMISSION_MATRIX.md
- Side-effect tools are blocked without permission
- All decisions are auditable with reason_code and policy_version
"""

from __future__ import annotations

from relic.hermes_plugin.fail_safe import FailSafeRegistry
from relic.hermes_plugin.hooks import HookEvent, HookManager, ToolCallContext
from relic.hermes_plugin.tool_permissions import ToolPermissionMatrix


class TestPreToolCallEnforcement:
    """Test pre_tool_call permission enforcement."""

    def test_pre_tool_call_allows_read_only(self) -> None:
        """Pre-tool-call should allow read-only tools."""
        matrix = ToolPermissionMatrix()
        registry = FailSafeRegistry()
        hooks = HookManager(permission_matrix=matrix, fail_safe=registry)

        context = ToolCallContext(
            tool_name="memory.read",
            is_roleplay=False,
        )
        result = hooks.pre_tool_call(context)
        assert result.allowed is True
        assert result.event == HookEvent.PRE_TOOL_CALL

    def test_pre_tool_call_blocks_l2_without_approval(self) -> None:
        """Pre-tool-call should block L2 tools in roleplay without approval."""
        matrix = ToolPermissionMatrix()
        registry = FailSafeRegistry()
        hooks = HookManager(permission_matrix=matrix, fail_safe=registry)

        context = ToolCallContext(
            tool_name="memory.delete",
            is_roleplay=True,
            explicit_approval=False,
        )
        result = hooks.pre_tool_call(context)
        assert result.allowed is False
        assert result.event == HookEvent.TOOL_BLOCKED

    def test_pre_tool_call_allows_l2_with_approval(self) -> None:
        """Pre-tool-call should allow L2 with explicit approval."""
        matrix = ToolPermissionMatrix()
        registry = FailSafeRegistry()
        hooks = HookManager(permission_matrix=matrix, fail_safe=registry)

        context = ToolCallContext(
            tool_name="memory.delete",
            is_roleplay=True,
            explicit_approval=True,
        )
        result = hooks.pre_tool_call(context)
        assert result.allowed is True

    def test_pre_tool_call_blocks_l3(self) -> None:
        """Pre-tool-call should block L3 tools."""
        matrix = ToolPermissionMatrix()
        registry = FailSafeRegistry()
        hooks = HookManager(permission_matrix=matrix, fail_safe=registry)

        context = ToolCallContext(tool_name="tool.execute")
        result = hooks.pre_tool_call(context)
        assert result.allowed is False
        assert result.event == HookEvent.TOOL_BLOCKED

    def test_pre_tool_call_blocks_lab_promote(self) -> None:
        """Pre-tool-call should block lab.promote (side-effect gate)."""
        matrix = ToolPermissionMatrix()
        registry = FailSafeRegistry()
        hooks = HookManager(permission_matrix=matrix, fail_safe=registry)

        context = ToolCallContext(tool_name="lab.promote")
        result = hooks.pre_tool_call(context)
        assert result.allowed is False


class TestPreToolCallAudit:
    """Test pre_tool_call audit trail."""

    def test_pre_tool_call_records_reason_code(self) -> None:
        """Pre-tool-call should record reason code."""
        matrix = ToolPermissionMatrix()
        registry = FailSafeRegistry()
        hooks = HookManager(permission_matrix=matrix, fail_safe=registry)

        context = ToolCallContext(tool_name="memory.read")
        result = hooks.pre_tool_call(context)
        assert result.reason_code is not None
        # Check it's a valid reason code
        assert "Permission" in result.reason_code or "GRANTED" in result.reason_code or "granted" in result.reason_code.lower()

    def test_pre_tool_call_records_policy_version(self) -> None:
        """Pre-tool-call should record policy version."""
        matrix = ToolPermissionMatrix(policy_version="1.0.0")
        registry = FailSafeRegistry()
        hooks = HookManager(permission_matrix=matrix, fail_safe=registry)

        context = ToolCallContext(tool_name="memory.read")
        result = hooks.pre_tool_call(context)
        assert result.policy_version == "1.0.0"

    def test_pre_tool_call_records_trace_id(self) -> None:
        """Pre-tool-call should record trace ID."""
        matrix = ToolPermissionMatrix()
        registry = FailSafeRegistry()
        hooks = HookManager(permission_matrix=matrix, fail_safe=registry)

        context = ToolCallContext(tool_name="memory.read")
        result = hooks.pre_tool_call(context)
        assert result.trace_id is not None
        assert result.trace_id == context.trace_id

    def test_pre_tool_call_audit_log_contains_entry(self) -> None:
        """Audit log should contain entry for each call."""
        matrix = ToolPermissionMatrix()
        registry = FailSafeRegistry()
        hooks = HookManager(permission_matrix=matrix, fail_safe=registry)

        context = ToolCallContext(tool_name="memory.read")
        hooks.pre_tool_call(context)

        log = hooks.get_audit_log()
        assert len(log) == 1
        assert log[0].tool_name == "memory.read"

    def test_pre_tool_call_audit_has_no_raw_content(self) -> None:
        """Audit log should have no raw content."""
        matrix = ToolPermissionMatrix()
        registry = FailSafeRegistry()
        hooks = HookManager(permission_matrix=matrix, fail_safe=registry)

        # Even with tool args that might have sensitive info
        context = ToolCallContext(
            tool_name="memory.read",
            tool_args={"content": "sensitive data"},
            user_intent_raw="I want to read my private memory",
        )
        hooks.pre_tool_call(context)

        log = hooks.get_audit_log()
        assert len(log) == 1
        # Sanitized metadata should not have raw content
        log_str = str(log[0].sanitized_metadata) if log[0].sanitized_metadata else ""
        assert "sensitive data" not in log_str


class TestPreToolCallFailSafeIntegration:
    """Test pre_tool_call fail-safe integration."""

    def test_fail_safe_triggered_on_l2_blocked(self) -> None:
        """Fail-safe should be triggered on L2 blocked."""
        matrix = ToolPermissionMatrix()
        registry = FailSafeRegistry()
        hooks = HookManager(permission_matrix=matrix, fail_safe=registry)

        context = ToolCallContext(
            tool_name="memory.delete",
            is_roleplay=True,
            explicit_approval=False,
        )
        hooks.pre_tool_call(context)

        # Fail-safe should be triggered for L2 blocked
        assert registry.is_triggered is True

    def test_fail_safe_triggered_on_l3_blocked(self) -> None:
        """Fail-safe should be triggered on L3 blocked."""
        matrix = ToolPermissionMatrix()
        registry = FailSafeRegistry()
        hooks = HookManager(permission_matrix=matrix, fail_safe=registry)

        context = ToolCallContext(tool_name="tool.execute")
        hooks.pre_tool_call(context)

        assert registry.is_triggered is True

    def test_fail_safe_not_triggered_for_allowed_tools(self) -> None:
        """Fail-safe should not trigger for allowed tools."""
        matrix = ToolPermissionMatrix()
        registry = FailSafeRegistry()
        hooks = HookManager(permission_matrix=matrix, fail_safe=registry)

        context = ToolCallContext(tool_name="memory.read")
        hooks.pre_tool_call(context)

        assert registry.is_triggered is False

    def test_fail_safe_not_triggered_when_disabled(self) -> None:
        """Fail-safe should not trigger when disabled."""
        matrix = ToolPermissionMatrix()
        registry = FailSafeRegistry(enabled=False)
        hooks = HookManager(permission_matrix=matrix, fail_safe=registry)

        context = ToolCallContext(tool_name="tool.execute")
        hooks.pre_tool_call(context)

        # Should still block, but not trigger fail-safe
        assert registry.is_triggered is False


class TestPreToolCallBlockedTools:
    """Test blocked tool handling."""

    def test_blocked_tool_has_blocked_reason(self) -> None:
        """Blocked tools should have blocked reason."""
        matrix = ToolPermissionMatrix()
        registry = FailSafeRegistry()
        hooks = HookManager(permission_matrix=matrix, fail_safe=registry)

        context = ToolCallContext(
            tool_name="memory.delete",
            is_roleplay=True,
            explicit_approval=False,
        )
        result = hooks.pre_tool_call(context)
        assert result.blocked_reason is not None

    def test_blocked_tool_event_logged(self) -> None:
        """Blocked tool should be logged with TOOL_BLOCKED event."""
        matrix = ToolPermissionMatrix()
        registry = FailSafeRegistry()
        hooks = HookManager(permission_matrix=matrix, fail_safe=registry)

        context = ToolCallContext(
            tool_name="memory.delete",
            is_roleplay=True,
            explicit_approval=False,
        )
        hooks.pre_tool_call(context)

        log = hooks.get_audit_log()
        blocked_events = [e for e in log if e.event == HookEvent.TOOL_BLOCKED]
        assert len(blocked_events) == 1

    def test_get_last_blocked_reason(self) -> None:
        """Should get last blocked reason."""
        matrix = ToolPermissionMatrix()
        registry = FailSafeRegistry()
        hooks = HookManager(permission_matrix=matrix, fail_safe=registry)

        context = ToolCallContext(
            tool_name="memory.delete",
            is_roleplay=True,
            explicit_approval=False,
        )
        hooks.pre_tool_call(context)

        reason = hooks.get_last_blocked_reason()
        assert reason is not None
        assert "memory.delete" in reason or "roleplay" in reason.lower()
