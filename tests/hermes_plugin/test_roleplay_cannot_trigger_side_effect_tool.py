"""Tests for roleplay mode restrictions.

These tests verify:
- Roleplay mode cannot trigger L2+ side-effect tools
- Explicit approval is required for L2 in roleplay
- L3 tools always require approval
- Filesystem, network, email, calendar, shell tools are blocked
"""

from __future__ import annotations

from relic.hermes_plugin.hooks import HookManager, ToolCallContext
from relic.hermes_plugin.tool_permissions import ToolPermissionMatrix


class TestRoleplayBlocksL2Tools:
    """Test roleplay mode blocks L2 tools."""

    def test_roleplay_blocks_memory_delete(self) -> None:
        """Roleplay should block memory.delete."""
        matrix = ToolPermissionMatrix()
        hooks = HookManager(permission_matrix=matrix)

        context = ToolCallContext(
            tool_name="memory.delete",
            is_roleplay=True,
            explicit_approval=False,
        )
        result = hooks.pre_tool_call(context)
        assert result.allowed is False

    def test_roleplay_blocks_provider_call(self) -> None:
        """Roleplay should block provider.call."""
        matrix = ToolPermissionMatrix()
        hooks = HookManager(permission_matrix=matrix)

        context = ToolCallContext(
            tool_name="provider.call",
            is_roleplay=True,
            explicit_approval=False,
        )
        result = hooks.pre_tool_call(context)
        assert result.allowed is False

    def test_roleplay_blocks_filesystem_write(self) -> None:
        """Roleplay should block filesystem.write."""
        matrix = ToolPermissionMatrix()
        hooks = HookManager(permission_matrix=matrix)

        context = ToolCallContext(
            tool_name="filesystem.write",
            is_roleplay=True,
            explicit_approval=False,
        )
        result = hooks.pre_tool_call(context)
        assert result.allowed is False

    def test_roleplay_blocks_network_http(self) -> None:
        """Roleplay should block network.http."""
        matrix = ToolPermissionMatrix()
        hooks = HookManager(permission_matrix=matrix)

        context = ToolCallContext(
            tool_name="network.http",
            is_roleplay=True,
            explicit_approval=False,
        )
        result = hooks.pre_tool_call(context)
        assert result.allowed is False

    def test_roleplay_blocks_email_send(self) -> None:
        """Roleplay should block email.send."""
        matrix = ToolPermissionMatrix()
        hooks = HookManager(permission_matrix=matrix)

        context = ToolCallContext(
            tool_name="email.send",
            is_roleplay=True,
            explicit_approval=False,
        )
        result = hooks.pre_tool_call(context)
        assert result.allowed is False

    def test_roleplay_blocks_calendar_event(self) -> None:
        """Roleplay should block calendar.event."""
        matrix = ToolPermissionMatrix()
        hooks = HookManager(permission_matrix=matrix)

        context = ToolCallContext(
            tool_name="calendar.event",
            is_roleplay=True,
            explicit_approval=False,
        )
        result = hooks.pre_tool_call(context)
        assert result.allowed is False


class TestRoleplayBlocksL3Tools:
    """Test roleplay mode blocks L3 tools (even with approval)."""

    def test_roleplay_blocks_shell_execute(self) -> None:
        """Roleplay should block shell.execute even with approval."""
        matrix = ToolPermissionMatrix()
        hooks = HookManager(permission_matrix=matrix)

        context = ToolCallContext(
            tool_name="shell.execute",
            is_roleplay=True,
            explicit_approval=True,  # Even with approval
        )
        result = hooks.pre_tool_call(context)
        assert result.allowed is False
        assert "L3" in result.reason_code or "security" in result.reason_code.lower()

    def test_roleplay_blocks_tool_execute(self) -> None:
        """Roleplay should block tool.execute even with approval."""
        matrix = ToolPermissionMatrix()
        hooks = HookManager(permission_matrix=matrix)

        context = ToolCallContext(
            tool_name="tool.execute",
            is_roleplay=True,
            explicit_approval=True,
        )
        result = hooks.pre_tool_call(context)
        assert result.allowed is False


class TestExplicitApprovalOverridesRoleplay:
    """Test explicit approval overrides roleplay for L2."""

    def test_explicit_approval_allows_memory_delete(self) -> None:
        """Explicit approval should allow memory.delete in roleplay."""
        matrix = ToolPermissionMatrix()
        hooks = HookManager(permission_matrix=matrix)

        context = ToolCallContext(
            tool_name="memory.delete",
            is_roleplay=True,
            explicit_approval=True,
        )
        result = hooks.pre_tool_call(context)
        assert result.allowed is True

    def test_explicit_approval_allows_provider_call(self) -> None:
        """Explicit approval should allow provider.call in roleplay."""
        matrix = ToolPermissionMatrix()
        hooks = HookManager(permission_matrix=matrix)

        context = ToolCallContext(
            tool_name="provider.call",
            is_roleplay=True,
            explicit_approval=True,
        )
        result = hooks.pre_tool_call(context)
        assert result.allowed is True

    def test_explicit_approval_allows_filesystem_write(self) -> None:
        """Explicit approval should allow filesystem.write in roleplay."""
        matrix = ToolPermissionMatrix()
        hooks = HookManager(permission_matrix=matrix)

        context = ToolCallContext(
            tool_name="filesystem.write",
            is_roleplay=True,
            explicit_approval=True,
        )
        result = hooks.pre_tool_call(context)
        assert result.allowed is True


class TestRoleplayAllowsReadOnlyTools:
    """Test roleplay mode allows read-only tools."""

    def test_roleplay_allows_memory_read(self) -> None:
        """Roleplay should allow memory.read."""
        matrix = ToolPermissionMatrix()
        hooks = HookManager(permission_matrix=matrix)

        context = ToolCallContext(
            tool_name="memory.read",
            is_roleplay=True,
            explicit_approval=False,
        )
        result = hooks.pre_tool_call(context)
        assert result.allowed is True

    def test_roleplay_allows_context_read(self) -> None:
        """Roleplay should allow context.read."""
        matrix = ToolPermissionMatrix()
        hooks = HookManager(permission_matrix=matrix)

        context = ToolCallContext(
            tool_name="context.read",
            is_roleplay=True,
            explicit_approval=False,
        )
        result = hooks.pre_tool_call(context)
        assert result.allowed is True

    def test_roleplay_allows_provider_list(self) -> None:
        """Roleplay should allow provider.list."""
        matrix = ToolPermissionMatrix()
        hooks = HookManager(permission_matrix=matrix)

        context = ToolCallContext(
            tool_name="provider.list",
            is_roleplay=True,
            explicit_approval=False,
        )
        result = hooks.pre_tool_call(context)
        assert result.allowed is True


class TestRoleplayAllowsWriteOnceTools:
    """Test roleplay mode allows write-once tools."""

    def test_roleplay_allows_memory_append(self) -> None:
        """Roleplay should allow memory.append."""
        matrix = ToolPermissionMatrix()
        hooks = HookManager(permission_matrix=matrix)

        context = ToolCallContext(
            tool_name="memory.append",
            is_roleplay=True,
            explicit_approval=False,
        )
        result = hooks.pre_tool_call(context)
        assert result.allowed is True

    def test_roleplay_allows_audit_log(self) -> None:
        """Roleplay should allow audit.log."""
        matrix = ToolPermissionMatrix()
        hooks = HookManager(permission_matrix=matrix)

        context = ToolCallContext(
            tool_name="audit.log",
            is_roleplay=True,
            explicit_approval=False,
        )
        result = hooks.pre_tool_call(context)
        assert result.allowed is True


class TestNonRoleplayMode:
    """Test non-roleplay mode behavior."""

    def test_non_roleplay_allows_l2_tools(self) -> None:
        """Non-roleplay should allow L2 tools."""
        matrix = ToolPermissionMatrix()
        hooks = HookManager(permission_matrix=matrix)

        context = ToolCallContext(
            tool_name="memory.delete",
            is_roleplay=False,
            explicit_approval=False,
        )
        result = hooks.pre_tool_call(context)
        assert result.allowed is True

    def test_non_roleplay_allows_provider_call(self) -> None:
        """Non-roleplay should allow provider.call."""
        matrix = ToolPermissionMatrix()
        hooks = HookManager(permission_matrix=matrix)

        context = ToolCallContext(
            tool_name="provider.call",
            is_roleplay=False,
            explicit_approval=False,
        )
        result = hooks.pre_tool_call(context)
        assert result.allowed is True

    def test_non_roleplay_still_blocks_l3(self) -> None:
        """Non-roleplay should still block L3 tools."""
        matrix = ToolPermissionMatrix()
        hooks = HookManager(permission_matrix=matrix)

        context = ToolCallContext(
            tool_name="tool.execute",
            is_roleplay=False,
            explicit_approval=False,
        )
        result = hooks.pre_tool_call(context)
        assert result.allowed is False
