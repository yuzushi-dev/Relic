"""Tool permission matrix enforcement.

This module implements the TOOL_PERMISSION_MATRIX.md enforcement
for the Hermes plugin. It provides:

1. Permission checking before side-effect tool execution
2. Roleplay mode restrictions (L2+ tools blocked without approval)
3. Audit trail with reason_code and policy_version

Key guarantees:
- No side-effect tool executes without permission decision
- Roleplay mode cannot trigger L2+ tools without explicit approval
- All decisions are auditable with reason_code and policy_version
- No raw prompts or private text in audit logs
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class ToolCategory(str, Enum):
    """Tool categories per TOOL_PERMISSION_MATRIX.md."""
    READ_ONLY = "read_only"
    WRITE_ONCE = "write_once"
    SIDE_EFFECT_L1 = "side_effect_l1"  # Low risk side effects
    SIDE_EFFECT_L2 = "side_effect_l2"  # Medium risk - blocked in roleplay
    SIDE_EFFECT_L3 = "side_effect_l3"  # High risk - always blocked without approval


@dataclass
class PermissionScope:
    """Required permission scopes for a tool."""
    required: list[str] = field(default_factory=list)
    optional: list[str] = field(default_factory=list)


@dataclass
class PermissionResult:
    """Result of a permission check."""
    allowed: bool
    tool_name: str
    category: ToolCategory
    reason_code: str
    policy_version: str
    blocked_reason: str | None = None
    required_scopes: list[str] = field(default_factory=list)
    timestamp: datetime | None = None
    metadata: dict[str, Any] | None = None


# Tool category mapping (from TOOL_PERMISSION_MATRIX.md)
TOOL_CATEGORY_MAP: dict[str, ToolCategory] = {
    # Read-only tools
    "memory.read": ToolCategory.READ_ONLY,
    "context.read": ToolCategory.READ_ONLY,
    "provider.list": ToolCategory.READ_ONLY,
    # Write-once tools
    "memory.append": ToolCategory.WRITE_ONCE,
    "audit.log": ToolCategory.WRITE_ONCE,
    # Side-effect L1 (low risk)
    "memory.update": ToolCategory.SIDE_EFFECT_L1,
    # Side-effect L2 (medium risk - blocked in roleplay)
    "memory.delete": ToolCategory.SIDE_EFFECT_L2,
    "provider.call": ToolCategory.SIDE_EFFECT_L2,
    # Side-effect L3 (high risk - always blocked)
    "tool.execute": ToolCategory.SIDE_EFFECT_L3,
    "lab.promote": ToolCategory.SIDE_EFFECT_L3,  # blocked: lab promotion is a privileged side-effect
    # Additional filesystem/network tools
    "filesystem.write": ToolCategory.SIDE_EFFECT_L2,
    "filesystem.read": ToolCategory.READ_ONLY,
    "network.http": ToolCategory.SIDE_EFFECT_L2,
    "email.send": ToolCategory.SIDE_EFFECT_L2,
    "calendar.event": ToolCategory.SIDE_EFFECT_L2,
    "shell.execute": ToolCategory.SIDE_EFFECT_L3,
}


# Reason codes for audit trail
REASON_CODES = {
    # Permission granted
    "PERMISSION_GRANTED": "Permission check passed",
    "ROLEPLAY_APPROVED": "Roleplay mode with explicit approval",
    # Permission denied
    "ROLEPLAY_BLOCKED": "Roleplay mode blocks L2+ tools without approval",
    "L3_BLOCKED": "L3 tools require security override",
    "TOOL_UNKNOWN": "Tool not in permission matrix",
    "CATEGORY_MISSING": "Tool category not defined",
}


@dataclass
class ToolPermissionMatrix:
    """Tool permission matrix with enforcement.

    This matrix enforces TOOL_PERMISSION_MATRIX.md rules:
    - Read-only and write-once tools are allowed
    - Side-effect L1 tools require permission
    - Side-effect L2 tools are blocked in roleplay without approval
    - Side-effect L3 tools require security override
    """

    def __init__(
        self,
        matrix_path: Path | None = None,
        policy_version: str = "1.0.0",
    ) -> None:
        self._matrix_path = matrix_path
        self._policy_version = policy_version
        self._category_map = dict(TOOL_CATEGORY_MAP)

    @property
    def policy_version(self) -> str:
        """Get the policy version for audit."""
        return self._policy_version

    def check_permission(
        self,
        tool_name: str,
        is_roleplay: bool = False,
        explicit_approval: bool = False,
    ) -> PermissionResult:
        """Check if a tool call is permitted.

        Args:
            tool_name: Name of the tool
            is_roleplay: Whether the session is in roleplay mode
            explicit_approval: Whether explicit non-roleplay user approval exists

        Returns:
            PermissionResult with decision and audit info
        """
        # Get tool category
        category = self._category_map.get(tool_name)

        if category is None:
            # Unknown tool - fail closed
            return PermissionResult(
                allowed=False,
                tool_name=tool_name,
                category=ToolCategory.SIDE_EFFECT_L3,  # Assume worst case
                reason_code=REASON_CODES["TOOL_UNKNOWN"],
                policy_version=self._policy_version,
                blocked_reason=f"Tool '{tool_name}' not in permission matrix",
            )

        # Check based on category
        if category == ToolCategory.READ_ONLY:
            return PermissionResult(
                allowed=True,
                tool_name=tool_name,
                category=category,
                reason_code=REASON_CODES["PERMISSION_GRANTED"],
                policy_version=self._policy_version,
                required_scopes=["context:read"],
            )

        if category == ToolCategory.WRITE_ONCE:
            return PermissionResult(
                allowed=True,
                tool_name=tool_name,
                category=category,
                reason_code=REASON_CODES["PERMISSION_GRANTED"],
                policy_version=self._policy_version,
                required_scopes=["context:write", "audit:write"],
            )

        if category == ToolCategory.SIDE_EFFECT_L1:
            return PermissionResult(
                allowed=True,
                tool_name=tool_name,
                category=category,
                reason_code=REASON_CODES["PERMISSION_GRANTED"],
                policy_version=self._policy_version,
                required_scopes=["memory:modify"],
            )

        if category == ToolCategory.SIDE_EFFECT_L2:
            # L2 tools blocked in roleplay without explicit approval
            if is_roleplay and not explicit_approval:
                return PermissionResult(
                    allowed=False,
                    tool_name=tool_name,
                    category=category,
                    reason_code=REASON_CODES["ROLEPLAY_BLOCKED"],
                    policy_version=self._policy_version,
                    blocked_reason=f"Tool '{tool_name}' (L2) blocked in roleplay mode without explicit approval",
                    required_scopes=["privacy:gate"],
                )
            return PermissionResult(
                allowed=True,
                tool_name=tool_name,
                category=category,
                reason_code=REASON_CODES["PERMISSION_GRANTED"]
                if not is_roleplay
                else REASON_CODES["ROLEPLAY_APPROVED"],
                policy_version=self._policy_version,
                required_scopes=["privacy:gate"],
            )

        if category == ToolCategory.SIDE_EFFECT_L3:
            # L3 tools always require approval (security override)
            return PermissionResult(
                allowed=False,
                tool_name=tool_name,
                category=category,
                reason_code=REASON_CODES["L3_BLOCKED"],
                policy_version=self._policy_version,
                blocked_reason=f"Tool '{tool_name}' (L3) requires security:override",
                required_scopes=["security:override"],
            )

        # Should not reach here, but fail closed
        return PermissionResult(
            allowed=False,
            tool_name=tool_name,
            category=category or ToolCategory.SIDE_EFFECT_L3,
            reason_code=REASON_CODES["CATEGORY_MISSING"],
            policy_version=self._policy_version,
            blocked_reason=f"Category handling error for '{tool_name}'",
        )

    def get_category(self, tool_name: str) -> ToolCategory | None:
        """Get the category for a tool."""
        return self._category_map.get(tool_name)

    def is_side_effect(self, tool_name: str) -> bool:
        """Check if a tool has side effects."""
        category = self.get_category(tool_name)
        if category is None:
            return True  # Unknown tools assume side effect
        return category in [
            ToolCategory.SIDE_EFFECT_L1,
            ToolCategory.SIDE_EFFECT_L2,
            ToolCategory.SIDE_EFFECT_L3,
        ]

    def get_allowed_tools(
        self,
        is_roleplay: bool = False,
        explicit_approval: bool = False,
    ) -> list[str]:
        """Get list of allowed tools for current mode."""
        allowed = []
        for tool_name in self._category_map:
            result = self.check_permission(
                tool_name,
                is_roleplay=is_roleplay,
                explicit_approval=explicit_approval,
            )
            if result.allowed:
                allowed.append(tool_name)
        return allowed


@dataclass
class PermissionDecision:
    """Internal permission decision for hook system."""
    allowed: bool
    tool_name: str
    category: ToolCategory
    reason_code: str
    policy_version: str
    blocked_reason: str | None = None
