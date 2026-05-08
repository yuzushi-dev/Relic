"""Pre/post tool call hooks for permission enforcement.

This module implements the hook system that enforces TOOL_PERMISSION_MATRIX.md
before any side-effect tool execution. The hook system:

1. Intercepts tool calls before execution
2. Checks permissions against the tool permission matrix
3. Blocks L2+ tools in roleplay mode without explicit approval
4. Ensures all decisions are auditable

Key guarantees:
- Tool permission decisions are auditable with reason_code and policy_version
- No side-effect tool executes without a permission decision
- Roleplay mode cannot trigger L2+ tools without approval
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from relic.hermes_plugin.tool_permissions import ToolCategory, ToolPermissionMatrix

if TYPE_CHECKING:
    from relic.hermes_plugin.fail_safe import FailSafeRegistry


class HookEvent(str, Enum):
    """Hook event types."""
    PRE_TOOL_CALL = "pre_tool_call"
    POST_TOOL_CALL = "post_tool_call"
    TOOL_BLOCKED = "tool_blocked"


@dataclass
class ToolCallContext:
    """Context for a tool call."""
    tool_name: str
    tool_args: dict[str, Any] | None = None
    session_id: str | None = None
    is_roleplay: bool = False
    explicit_approval: bool = False
    user_intent_raw: str | None = None  # NOT stored in audit logs
    timestamp: datetime | None = None
    trace_id: str | None = None


@dataclass
class HookResult:
    """Result of a hook execution."""
    allowed: bool
    event: HookEvent
    tool_name: str
    reason_code: str
    policy_version: str
    trace_id: str
    blocked_reason: str | None = None
    timestamp: datetime | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class HookAuditEntry:
    """Audit entry for a hook execution.

    This entry NEVER contains raw prompts, raw private text,
    or other sensitive content.
    """
    trace_id: str
    event: HookEvent
    tool_name: str
    allowed: bool
    reason_code: str
    policy_version: str
    tool_category: ToolCategory | None = None
    is_roleplay: bool = False
    explicit_approval: bool = False
    blocked_reason: str | None = None
    timestamp: datetime | None = None
    # Metadata is sanitized - no raw content
    sanitized_metadata: dict[str, Any] | None = None


class HookManager:
    """Manages pre/post tool call hooks.

    This manager enforces tool permissions before any side-effect
    tool execution. It is the gatekeeper for all tool calls.

    Guarantees:
    - Every side-effect tool call is checked against permission matrix
    - All decisions are auditable with reason_code and policy_version
    - Roleplay mode blocks L2+ tools without explicit approval
    - No raw prompts or private text appear in audit entries
    """

    def __init__(
        self,
        permission_matrix: ToolPermissionMatrix,
        fail_safe: FailSafeRegistry | None = None,
        roleplay_blocks_l2: bool = True,
    ) -> None:
        self._matrix = permission_matrix
        self._fail_safe = fail_safe
        self._roleplay_blocks_l2 = roleplay_blocks_l2
        self._audit_log: list[HookAuditEntry] = []

    def pre_tool_call(self, context: ToolCallContext) -> HookResult:
        """Check permissions before tool execution.

        This is the main entry point for permission enforcement.
        It MUST be called before any side-effect tool execution.

        Args:
            context: Tool call context with tool info

        Returns:
            HookResult indicating if the tool is allowed
        """
        # Normalize context
        if context.timestamp is None:
            context.timestamp = datetime.utcnow()
        if context.trace_id is None:
            context.trace_id = str(uuid4())
        if context.tool_args is None:
            context.tool_args = {}

        # Get permission decision
        permission_result = self._matrix.check_permission(
            tool_name=context.tool_name,
            is_roleplay=context.is_roleplay,
            explicit_approval=context.explicit_approval,
        )

        # Build audit entry (sanitized - no raw content)
        audit_entry = HookAuditEntry(
            trace_id=context.trace_id,
            event=HookEvent.PRE_TOOL_CALL,
            tool_name=context.tool_name,
            allowed=permission_result.allowed,
            reason_code=permission_result.reason_code,
            policy_version=permission_result.policy_version,
            tool_category=permission_result.category,
            is_roleplay=context.is_roleplay,
            explicit_approval=context.explicit_approval,
            blocked_reason=permission_result.blocked_reason,
            timestamp=context.timestamp,
            sanitized_metadata={
                # Never include raw prompts or private text
                "tool_args_keys": list(context.tool_args.keys()) if context.tool_args else [],
                "has_session_id": context.session_id is not None,
                "roleplay_blocks_enforced": self._roleplay_blocks_l2,
            },
        )
        self._audit_log.append(audit_entry)

        # Handle blocked tools
        if not permission_result.allowed:
            # Log blocked event
            blocked_audit = HookAuditEntry(
                trace_id=context.trace_id,
                event=HookEvent.TOOL_BLOCKED,
                tool_name=context.tool_name,
                allowed=False,
                reason_code=permission_result.reason_code,
                policy_version=permission_result.policy_version,
                tool_category=permission_result.category,
                is_roleplay=context.is_roleplay,
                explicit_approval=context.explicit_approval,
                blocked_reason=permission_result.blocked_reason,
                timestamp=context.timestamp,
                sanitized_metadata=audit_entry.sanitized_metadata,
            )
            self._audit_log.append(blocked_audit)

            # Trigger fail-safe if configured
            if self._fail_safe and permission_result.category in [
                ToolCategory.SIDE_EFFECT_L2,
                ToolCategory.SIDE_EFFECT_L3,
            ]:
                from relic.hermes_plugin.fail_safe import FailSafeTrigger
                self._fail_safe.trigger(
                    reason=f"Blocked {permission_result.category.value}: {permission_result.blocked_reason}",
                    trigger=FailSafeTrigger.PERMISSION_DENIED,
                    trace_id=context.trace_id,
                )

            return HookResult(
                allowed=False,
                event=HookEvent.TOOL_BLOCKED,
                tool_name=context.tool_name,
                reason_code=permission_result.reason_code,
                policy_version=permission_result.policy_version,
                trace_id=context.trace_id,
                blocked_reason=permission_result.blocked_reason,
            )

        return HookResult(
            allowed=True,
            event=HookEvent.PRE_TOOL_CALL,
            tool_name=context.tool_name,
            reason_code=permission_result.reason_code,
            policy_version=permission_result.policy_version,
            trace_id=context.trace_id,
        )

    def post_tool_call(
        self,
        context: ToolCallContext,
        success: bool,
        error: str | None = None,
    ) -> HookResult:
        """Post-tool-call hook for logging.

        This is called after tool execution to log the result.
        It does NOT make permission decisions (those are pre-tool-call only).
        """
        if context.timestamp is None:
            context.timestamp = datetime.utcnow()
        if context.trace_id is None:
            context.trace_id = str(uuid4())

        return HookResult(
            allowed=success,
            event=HookEvent.POST_TOOL_CALL,
            tool_name=context.tool_name,
            reason_code="post_execution_log",
            policy_version=self._matrix.policy_version,
            trace_id=context.trace_id,
            metadata={"success": success, "error": error},
        )

    def get_audit_log(self) -> list[HookAuditEntry]:
        """Get the audit log (for verification/debugging).

        Returns sanitized entries only - no raw content.
        """
        return list(self._audit_log)

    def clear_audit_log(self) -> None:
        """Clear the audit log (for testing)."""
        self._audit_log = []

    def get_last_blocked_reason(self) -> str | None:
        """Get the reason for the last blocked tool call."""
        for entry in reversed(self._audit_log):
            if entry.event == HookEvent.TOOL_BLOCKED:
                return entry.blocked_reason
        return None
