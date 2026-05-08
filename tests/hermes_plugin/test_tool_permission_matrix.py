"""Tests for tool permission matrix.

These tests verify:
- Tool permission matrix enforces TOOL_PERMISSION_MATRIX.md
- All decisions are auditable with reason_code and policy_version
- No raw prompts or private text in audit
"""

from __future__ import annotations

from relic.hermes_plugin.tool_permissions import (
    REASON_CODES,
    ToolCategory,
    ToolPermissionMatrix,
)


class TestToolPermissionMatrix:
    """Test tool permission matrix enforcement."""

    def test_matrix_has_policy_version(self) -> None:
        """Matrix should have policy version for audit."""
        matrix = ToolPermissionMatrix(policy_version="1.0.0")
        assert matrix.policy_version == "1.0.0"

    def test_read_only_tools_allowed(self) -> None:
        """Read-only tools should be allowed."""
        matrix = ToolPermissionMatrix()
        result = matrix.check_permission("memory.read")
        assert result.allowed is True
        assert result.category == ToolCategory.READ_ONLY

    def test_context_read_allowed(self) -> None:
        """context.read should be allowed."""
        matrix = ToolPermissionMatrix()
        result = matrix.check_permission("context.read")
        assert result.allowed is True

    def test_provider_list_allowed(self) -> None:
        """provider.list should be allowed."""
        matrix = ToolPermissionMatrix()
        result = matrix.check_permission("provider.list")
        assert result.allowed is True

    def test_write_once_tools_allowed(self) -> None:
        """Write-once tools should be allowed."""
        matrix = ToolPermissionMatrix()
        result = matrix.check_permission("memory.append")
        assert result.allowed is True
        assert result.category == ToolCategory.WRITE_ONCE

    def test_audit_log_allowed(self) -> None:
        """audit.log should be allowed."""
        matrix = ToolPermissionMatrix()
        result = matrix.check_permission("audit.log")
        assert result.allowed is True

    def test_l1_side_effect_allowed(self) -> None:
        """L1 side-effect tools should be allowed."""
        matrix = ToolPermissionMatrix()
        result = matrix.check_permission("memory.update")
        assert result.allowed is True
        assert result.category == ToolCategory.SIDE_EFFECT_L1

    def test_l2_side_effect_allowed_with_approval(self) -> None:
        """L2 side-effect tools allowed with approval."""
        matrix = ToolPermissionMatrix()
        result = matrix.check_permission(
            "memory.delete",
            is_roleplay=False,
            explicit_approval=True,
        )
        assert result.allowed is True

    def test_l2_side_effect_blocked_in_roleplay_without_approval(self) -> None:
        """L2 side-effect blocked in roleplay without approval."""
        matrix = ToolPermissionMatrix()
        result = matrix.check_permission(
            "memory.delete",
            is_roleplay=True,
            explicit_approval=False,
        )
        assert result.allowed is False
        assert result.reason_code == REASON_CODES["ROLEPLAY_BLOCKED"]

    def test_l3_side_effect_blocked(self) -> None:
        """L3 side-effect tools should be blocked."""
        matrix = ToolPermissionMatrix()
        result = matrix.check_permission("tool.execute")
        assert result.allowed is False
        assert result.reason_code == REASON_CODES["L3_BLOCKED"]

    def test_lab_promote_blocked(self) -> None:
        """lab.promote should be blocked (side-effect gate)."""
        matrix = ToolPermissionMatrix()
        result = matrix.check_permission("lab.promote")
        assert result.allowed is False
        assert result.reason_code == REASON_CODES["L3_BLOCKED"]

    def test_unknown_tool_blocked(self) -> None:
        """Unknown tools should be blocked."""
        matrix = ToolPermissionMatrix()
        result = matrix.check_permission("unknown.tool")
        assert result.allowed is False
        assert result.reason_code == REASON_CODES["TOOL_UNKNOWN"]


class TestAuditTrail:
    """Verify audit trail has no raw content."""

    def test_permission_result_has_reason_code(self) -> None:
        """Permission result should have reason code."""
        matrix = ToolPermissionMatrix()
        result = matrix.check_permission("memory.read")
        assert result.reason_code is not None
        assert "Permission" in result.reason_code or "GRANTED" in result.reason_code

    def test_permission_result_has_policy_version(self) -> None:
        """Permission result should have policy version."""
        matrix = ToolPermissionMatrix(policy_version="1.0.0")
        result = matrix.check_permission("memory.read")
        assert result.policy_version == "1.0.0"

    def test_blocked_result_has_blocked_reason(self) -> None:
        """Blocked result should have blocked reason."""
        matrix = ToolPermissionMatrix()
        result = matrix.check_permission(
            "memory.delete",
            is_roleplay=True,
            explicit_approval=False,
        )
        assert result.blocked_reason is not None
        # Should not contain raw content
        assert "raw" not in result.blocked_reason.lower()

    def test_no_raw_prompt_in_result(self) -> None:
        """Result should not contain raw prompt."""
        matrix = ToolPermissionMatrix()
        # Pass a tool name that would normally include prompt info
        result = matrix.check_permission("context.read")
        # Result should only have metadata, no raw content
        metadata_str = str(result.metadata) if result.metadata else ""
        assert "raw_prompt" not in metadata_str
        assert "raw_content" not in metadata_str

    def test_result_has_required_scopes(self) -> None:
        """Result should list required scopes."""
        matrix = ToolPermissionMatrix()
        result = matrix.check_permission("memory.read")
        assert result.required_scopes is not None
        assert isinstance(result.required_scopes, list)


class TestToolCategoryMapping:
    """Test tool category mapping."""

    def test_get_category_for_known_tool(self) -> None:
        """Should return category for known tools."""
        matrix = ToolPermissionMatrix()
        assert matrix.get_category("memory.read") == ToolCategory.READ_ONLY
        assert matrix.get_category("memory.append") == ToolCategory.WRITE_ONCE
        assert matrix.get_category("memory.delete") == ToolCategory.SIDE_EFFECT_L2

    def test_get_category_for_unknown_tool(self) -> None:
        """Should return None for unknown tools."""
        matrix = ToolPermissionMatrix()
        assert matrix.get_category("unknown.tool") is None

    def test_is_side_effect_for_known_tool(self) -> None:
        """Should correctly identify side-effect tools."""
        matrix = ToolPermissionMatrix()
        assert matrix.is_side_effect("memory.read") is False
        assert matrix.is_side_effect("memory.delete") is True
        assert matrix.is_side_effect("tool.execute") is True

    def test_is_side_effect_for_unknown_tool(self) -> None:
        """Unknown tools should be treated as side-effect."""
        matrix = ToolPermissionMatrix()
        assert matrix.is_side_effect("unknown.tool") is True


class TestRoleplayRestrictions:
    """Test roleplay mode restrictions."""

    def test_roleplay_blocks_l2_provider_call(self) -> None:
        """Roleplay should block provider.call."""
        matrix = ToolPermissionMatrix()
        result = matrix.check_permission(
            "provider.call",
            is_roleplay=True,
            explicit_approval=False,
        )
        assert result.allowed is False
        assert result.category == ToolCategory.SIDE_EFFECT_L2

    def test_roleplay_blocks_l2_filesystem_write(self) -> None:
        """Roleplay should block filesystem.write."""
        matrix = ToolPermissionMatrix()
        result = matrix.check_permission(
            "filesystem.write",
            is_roleplay=True,
            explicit_approval=False,
        )
        assert result.allowed is False

    def test_roleplay_blocks_l2_email_send(self) -> None:
        """Roleplay should block email.send."""
        matrix = ToolPermissionMatrix()
        result = matrix.check_permission(
            "email.send",
            is_roleplay=True,
            explicit_approval=False,
        )
        assert result.allowed is False

    def test_roleplay_blocks_l2_shell_execute(self) -> None:
        """Roleplay should block shell.execute (L3)."""
        matrix = ToolPermissionMatrix()
        result = matrix.check_permission(
            "shell.execute",
            is_roleplay=True,
            explicit_approval=True,  # Even with approval
        )
        assert result.allowed is False
        assert result.category == ToolCategory.SIDE_EFFECT_L3

    def test_explicit_approval_overrides_roleplay_for_l2(self) -> None:
        """Explicit approval should override roleplay for L2."""
        matrix = ToolPermissionMatrix()
        result = matrix.check_permission(
            "memory.delete",
            is_roleplay=True,
            explicit_approval=True,
        )
        assert result.allowed is True
        assert "Approved" in result.reason_code or "approval" in result.reason_code.lower()
