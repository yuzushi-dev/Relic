"""Pre/post tool call hooks for permission enforcement and PCP injection.

This module implements the hook system that:
1. Enforces tool permissions before any side-effect tool execution
2. Injects PromptContextPack into pre_llm_call with fail-closed behavior
3. Provides redacted tracing for all PCP operations

Key guarantees:
- Tool permission decisions are auditable with reason_code and policy_version
- PCP injection is fail-closed - no injection if anything fails
- All traces are redacted - no raw content stored
- No side-effect tool executes without a permission decision
"""

from __future__ import annotations

from dataclasses import dataclass, field
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
    PRE_LLM_CALL = "pre_llm_call"
    PCP_INJECTION = "pcp_injection"


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
class LLMSessionContext:
    """Context for an LLM call session."""
    session_id: str
    turn_id: str | None = None
    trace_id: str | None = None
    task_type: str = "technical"
    is_roleplay: bool = False
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.trace_id is None:
            self.trace_id = str(uuid4())
        if self.turn_id is None:
            self.turn_id = f"TURN-{uuid4().hex[:8]}"


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
    sanitized_metadata: dict[str, Any] | None = None


@dataclass
class PCPInjectionResult:
    """Result of PCP injection attempt."""
    success: bool
    trace_id: str
    context_pack: dict[str, Any] | None = None
    fail_closed: bool = False
    reason: str | None = None


class HookManager:
    """Manages pre/post tool call hooks and PCP injection.

    This manager:
    - Enforces tool permissions before any side-effect tool execution
    - Injects PromptContextPack into pre_llm_call with fail-closed behavior
    - All decisions are auditable with reason_code and policy_version

    Guarantees:
    - Every side-effect tool call is checked against permission matrix
    - PCP injection is fail-closed - no injection if anything fails
    - All traces are redacted - no raw content
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
        self._pcp_builder = None  # Lazy loaded
        self._pcp_trace = None  # Lazy loaded

    def _get_pcp_builder(self):
        """Lazy load PCP builder."""
        if self._pcp_builder is None:
            from relic.context_pack.builder import PCPBuilder
            from relic.context_pack.trace import PCPTrace
            self._pcp_trace = PCPTrace()
            self._pcp_builder = PCPBuilder(
                fail_safe=self._fail_safe,
                trace=self._pcp_trace,
            )
        return self._pcp_builder

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

    def pre_llm_call(self, context: LLMSessionContext) -> PCPInjectionResult:
        """Inject PromptContextPack before LLM call.

        This is the main entry point for PCP injection with fail-closed behavior.
        If anything goes wrong, no injection occurs.

        Args:
            context: LLM session context

        Returns:
            PCPInjectionResult with context pack or fail-closed result
        """
        trace_id = context.trace_id or str(uuid4())

        try:
            # Check fail-safe first
            if self._fail_safe and self._fail_safe.is_triggered:
                return PCPInjectionResult(
                    success=False,
                    trace_id=trace_id,
                    context_pack=None,
                    fail_closed=True,
                    reason="fail_safe_triggered",
                )

            # Build PCP
            from relic.context_pack.builder import (
                PCPBuilder,
                TaskType,
                RoleplayLevel,
                ContinuityMode,
            )

            # Map task type
            try:
                task_type = TaskType(context.task_type)
            except ValueError:
                task_type = TaskType.TECHNICAL

            builder = self._get_pcp_builder()
            pcp = builder.build(
                session_id=context.session_id,
                turn_id=context.turn_id,
                task_type=task_type,
                roleplay_level=RoleplayLevel.NORMAL if context.is_roleplay else RoleplayLevel.OFF,
                continuity_mode=ContinuityMode.COMPACT,
            )

            if pcp is None:
                # Fail-closed: build failed
                return PCPInjectionResult(
                    success=False,
                    trace_id=trace_id,
                    context_pack=None,
                    fail_closed=True,
                    reason="pcp_build_failed",
                )

            return PCPInjectionResult(
                success=True,
                trace_id=trace_id,
                context_pack=pcp.to_dict(),
                fail_closed=False,
                reason=None,
            )

        except Exception as exc:
            # Fail-closed on any exception
            return PCPInjectionResult(
                success=False,
                trace_id=trace_id,
                context_pack=None,
                fail_closed=True,
                reason=f"pre_llm_call_exception: {str(exc)}",
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

    def get_pcp_trace(self) -> list[dict[str, Any]]:
        """Get PCP construction trace for /relic why."""
        if self._pcp_trace:
            return self._pcp_trace.get_trace()
        return []
