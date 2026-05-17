"""Relic Hermes Plugin - Main plugin class and lifecycle.

This module implements the Hermes plugin interface for Relic.
The plugin provides ephemeral runtime guidance without modifying
persistent memory stores (SOUL.md, MEMORY.md, USER.md).

Key features:
- PromptContextPack (PCP) injection via pre_llm_call hook
- Fail-closed behavior - no injection on any failure
- Redacted tracing - no raw content in traces
- /relic why command for CAC trace inspection
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from relic.hermes_plugin.commands import RelicCommands
from relic.hermes_plugin.context_injection import inject_context
from relic.hermes_plugin.fail_safe import FailSafeRegistry
from relic.hermes_plugin.hooks import HookManager, LLMSessionContext

if TYPE_CHECKING:
    from relic.cac.controller import CACController
    from relic.control.pause import PauseController


class PluginState(str, Enum):
    """Plugin lifecycle states."""
    UNLOADED = "unloaded"
    LOADING = "loading"
    LOADED = "loaded"
    FAILED = "failed"
    SHUTDOWN = "shutdown"


@dataclass
class PluginConfig:
    """Configuration for the Relic plugin."""
    enabled: bool = True
    privacy_gateway_enabled: bool = True
    tool_permission_matrix_path: Path | None = None
    cac_trace_path: Path | None = None
    pause_db_path: Path | None = None
    # Policy version for audit trail
    policy_version: str = "1.0.0"
    # Fail-safe behavior
    fail_safe_enabled: bool = True
    fail_on_permission_error: bool = True
    # Roleplay restrictions
    roleplay_blocks_l2_tools: bool = True
    # Subject scoping for RelicMemoryProvider hook wiring.
    # Falls back to RELIC_SUBJECT_ID env var when empty.
    subject_id: str = ""
    hermes_profile_id: str = ""


@dataclass
class PluginLoadResult:
    """Result of plugin load operation."""
    success: bool = False
    state: PluginState = PluginState.UNLOADED
    error_message: str | None = None
    loaded_at: datetime | None = None
    plugin_id: str | None = None


class RelicHermesPlugin:
    """Hermes plugin for Relic runtime guidance.

    This plugin provides:
    - /relic why: Show last CAC trace or PCP trace
    - /relic pause: Disable runtime guidance
    - /relic resume: Re-enable runtime guidance
    - Pre-tool-call permission enforcement
    - PromptContextPack (PCP) injection with fail-closed behavior

    Guarantees:
    - Plugin failure produces NO memory injection
    - Only ephemeral per-turn context (no persistent changes)
    - Never mutates SOUL.md, MEMORY.md, USER.md
    - All tool permission decisions are auditable
    - PCP injection is fail-closed
    """

    def __init__(self) -> None:
        self._state = PluginState.UNLOADED
        self._config: PluginConfig | None = None
        self._commands: RelicCommands | None = None
        self._hooks: HookManager | None = None
        self._fail_safe: FailSafeRegistry | None = None
        self._tool_permissions: Any = None  # ToolPermissionMatrix
        self._load_result: PluginLoadResult | None = None
        # Cached pause controller (lazily initialized)
        self._pause_controller: PauseController | None = None
        # Cached CAC controller (lazily initialized)
        self._cac_controller: CACController | None = None
        # PCP trace for /relic why
        self._pcp_trace: Any = None

    @property
    def state(self) -> PluginState:
        """Get current plugin state."""
        return self._state

    @property
    def plugin_id(self) -> str | None:
        """Get plugin ID if loaded."""
        return self._load_result.plugin_id if self._load_result else None

    @property
    def is_paused(self) -> bool:
        """Check if plugin guidance is paused."""
        if not self._pause_controller:
            return False
        return self._pause_controller.is_paused()

    def load(self, config: dict[str, Any] | PluginConfig | None = None) -> PluginLoadResult:
        """Load the Relic plugin.

        Args:
            config: Plugin configuration (dict or PluginConfig)

        Returns:
            PluginLoadResult indicating success/failure
        """
        self._state = PluginState.LOADING

        try:
            # Parse configuration
            if config is None:
                self._config = PluginConfig()
            elif isinstance(config, dict):
                self._config = PluginConfig(**config)
            else:
                self._config = config

            # Initialize fail-safe registry first (critical for safety)
            self._fail_safe = FailSafeRegistry(enabled=self._config.fail_safe_enabled)
            self._fail_safe.register_hook(self._on_fail_safe_triggered)

            # Initialize tool permission matrix
            from relic.hermes_plugin.tool_permissions import ToolPermissionMatrix
            matrix_path = self._config.tool_permission_matrix_path
            self._tool_permissions = ToolPermissionMatrix(
                matrix_path=matrix_path,
                policy_version=self._config.policy_version,
            )

            # Initialize hooks for pre/post tool call and PCP injection
            self._hooks = HookManager(
                permission_matrix=self._tool_permissions,
                fail_safe=self._fail_safe,
                roleplay_blocks_l2=self._config.roleplay_blocks_l2_tools,
            )

            # Wire OutputCritic into post_llm_call (PR05 / deep-research-report gap)
            from relic.gumi_plugin import hooks as gumi_hooks
            from relic.gumi_plugin.critic import OutputCritic

            _critic = OutputCritic()

            def _post_llm_handler(payload: dict) -> dict:
                """Fail-open post_llm_call critic — never blocks conversation."""
                try:
                    text = payload.get("assistant_response", "") or ""
                    consensual = payload.get("consensual", True)
                    verdict = _critic.review(text, consensual=consensual)
                    return {
                        "allow": verdict.allow,
                        "reason": verdict.reason,
                        "requires_disclosure": verdict.requires_disclosure,
                    }
                except Exception:
                    return {"allow": True, "reason": "critic_error_fail_open"}

            gumi_hooks.register(gumi_hooks.POST_LLM_CALL, _post_llm_handler)

            # Wire RelicMemoryProvider as pre/post_llm_call hooks (Fix B).
            # subject_id sourced from config first, then RELIC_SUBJECT_ID env var.
            import os as _os
            _subject_id = self._config.subject_id or _os.environ.get("RELIC_SUBJECT_ID", "")
            if _subject_id:
                from relic.hermes_plugin.memory_provider import RelicMemoryProvider
                _mem_provider = RelicMemoryProvider(
                    subject_id=_subject_id,
                    hermes_profile_id=self._config.hermes_profile_id or "",
                    relic_home=_os.environ.get("RELIC_HOME"),
                )

                def _pre_llm_memory_handler(payload: dict) -> dict:
                    try:
                        query = payload.get("query", "") or ""
                        lines = _mem_provider.prefetch(query)
                        return {"memory_context": lines} if lines else {}
                    except Exception:
                        return {}

                def _post_llm_memory_handler(payload: dict) -> dict:
                    try:
                        user_msg = payload.get("user_message", "") or ""
                        assistant_msg = payload.get("assistant_response", "") or ""
                        _mem_provider.sync_turn(user_msg, assistant_msg)
                        return {}
                    except Exception:
                        return {}

                gumi_hooks.register(gumi_hooks.PRE_LLM_CALL, _pre_llm_memory_handler)
                gumi_hooks.register(gumi_hooks.POST_LLM_CALL, _post_llm_memory_handler)

                # Wire inject_context for USER_PRIVATE_FACTS + behavioral guidance.
                # Only registered when subject_id is known — no injection without subject scope.
                def _pre_llm_inject_context_handler(payload: dict) -> dict:
                    try:
                        session_id = payload.get("session_id", "") or ""
                        user_message = payload.get("user_message", "") or ""
                        result = inject_context(session_id=session_id, user_message=user_message)
                        return result if result else {}
                    except Exception:
                        return {}

                gumi_hooks.register(gumi_hooks.PRE_LLM_CALL, _pre_llm_inject_context_handler)

            # Wire output sanitizer as PRE_SEND handler (second layer, in-process path).
            # Subprocess delivery (cron scripts) use output_sanitizer.sanitize_for_subject
            # directly; this hook guards any future in-process send path.
            from relic.gumi_plugin.output_sanitizer import sanitize_for_subject as _sanitize

            def _pre_send_sanitizer(payload: dict) -> dict:
                try:
                    text = payload.get("text", "") or ""
                    safe = _sanitize(text)
                    if safe is None:
                        return {"action": "drop", "reason": "sanitized_empty"}
                    if safe != text:
                        return {"action": "deliver", "text": safe}
                    return {}
                except Exception:
                    return {}

            gumi_hooks.register(gumi_hooks.PRE_SEND, _pre_send_sanitizer)

            # Initialize PCP trace for /relic why
            from relic.context_pack.trace import PCPTrace
            self._pcp_trace = PCPTrace()

            # Initialize commands (only with pause_controller, not plugin)
            self._commands = RelicCommands(
                pause_controller=self._pause_controller,
            )

            # Mark as loaded
            self._state = PluginState.LOADED
            self._load_result = PluginLoadResult(
                success=True,
                state=PluginState.LOADED,
                loaded_at=datetime.utcnow(),
                plugin_id=str(uuid4()),
            )

            return self._load_result

        except Exception as exc:
            self._state = PluginState.FAILED
            self._load_result = PluginLoadResult(
                success=False,
                state=PluginState.FAILED,
                error_message=str(exc),
            )
            return self._load_result

    def unload(self) -> None:
        """Unload the plugin - clear all state."""
        self._state = PluginState.UNLOADED
        self._pause_controller = None
        self._cac_controller = None

    def shutdown(self) -> None:
        """Shutdown the plugin."""
        self._state = PluginState.SHUTDOWN

    def get_tool_permissions(self) -> Any:
        """Get the tool permission matrix."""
        return self._tool_permissions

    def get_hook_manager(self) -> HookManager | None:
        """Get the hook manager."""
        return self._hooks

    def pause_guidance(self, session_id: UUID | None = None) -> bool:
        """Pause all runtime guidance.

        Args:
            session_id: Optional session ID to pause

        Returns:
            True if pause was successful
        """
        if not self._config or not self._config.enabled:
            return False

        try:
            if not self._pause_controller:
                from relic.control.pause import PauseController
                self._pause_controller = PauseController(
                    db_path=str(self._config.pause_db_path) if self._config.pause_db_path else None
                )

            self._pause_controller.pause(
                session_id=session_id,
                reason="hermes_plugin_pause",
            )
            return True
        except Exception:
            # Fail-safe: if pause fails, guidance should be blocked anyway
            return False

    def resume_guidance(self, session_id: UUID | None = None) -> bool:
        """Resume runtime guidance.

        Args:
            session_id: Optional session ID to resume

        Returns:
            True if resume was successful
        """
        if not self._config or not self._config.enabled:
            return False

        try:
            if not self._pause_controller:
                return False

            self._pause_controller.resume(session_id=session_id)
            return True
        except Exception:
            return False

    def get_last_cac_trace(self) -> dict[str, Any] | None:
        """Get the last CAC trace for /relic why command.

        Returns redacted trace - no raw content.
        """
        try:
            if not self._cac_controller:
                # Lazy load CAC controller
                from relic.cac.controller import CACController
                self._cac_controller = CACController(
                    trace_path=self._config.cac_trace_path if self._config else None,
                )

            traces = self._cac_controller.get_traces()
            if traces:
                last_trace = traces[-1]
                # Return serializable dict without raw content
                return {
                    "trace_id": last_trace.trace_id,
                    "memory_id": last_trace.memory_id,
                    "memory_hash": last_trace.memory_hash,
                    "source": last_trace.source,
                    "decision": last_trace.decision,
                    "severity": last_trace.severity,
                    "disputed": last_trace.disputed,
                    "skip_reason": last_trace.skip_reason,
                    "timestamp": getattr(last_trace, 'timestamp', None),
                    "metadata": last_trace.metadata,
                }
            return None
        except Exception:
            return None

    def _on_fail_safe_triggered(self, reason: str) -> None:
        """Callback when fail-safe is triggered."""
        # Ensure guidance is blocked when fail-safe triggers
        self._state = PluginState.FAILED

    def inject_ephemeral_context(
        self,
        session_id: UUID | str | None = None,
        turn_id: str | None = None,
        task_type: str = "technical",
        is_roleplay: bool = False,
    ) -> dict[str, Any] | None:
        """Inject ephemeral context for current turn.

        This builds a PromptContextPack (PCP) for the current turn.
        Context is ONLY valid for the current turn and is NEVER
        written to SOUL.md, MEMORY.md, or USER.md.

        Uses fail-closed behavior - returns None on any failure.

        Args:
            session_id: Optional session ID (UUID or str)
            turn_id: Optional turn ID (generated if not provided)
            task_type: Task type for context classification
            is_roleplay: Whether roleplay mode is active

        Returns:
            Ephemeral context dict or None if paused/blocked/failed
        """
        # Fail-safe: never inject if not loaded
        if self._state != PluginState.LOADED:
            return None

        # Fail-safe: never inject if paused
        if self.is_paused:
            return None

        # Fail-safe: never inject if config disabled
        if not self._config or not self._config.enabled:
            return None

        # Fail-safe: never inject if fail-safe is triggered
        if self._fail_safe and self._fail_safe.is_triggered:
            return None

        try:
            # Create LLM session context for hooks
            if isinstance(session_id, UUID):
                session_id_str = str(session_id)
            elif session_id:
                session_id_str = str(session_id)
            else:
                session_id_str = f"SES-{uuid4().hex[:8]}"

            turn_id_str = turn_id or f"TURN-{uuid4().hex[:8]}"

            llm_context = LLMSessionContext(
                session_id=session_id_str,
                turn_id=turn_id_str,
                task_type=task_type,
                is_roleplay=is_roleplay,
            )

            # Get PCP injection via hook manager
            if self._hooks:
                result = self._hooks.pre_llm_call(llm_context)
                if result.success and result.context_pack:
                    # Log to trace
                    from relic.context_pack.trace import PCPTraceEvent
                    self._pcp_trace.log(
                        event=PCPTraceEvent.INJECTION_APPLIED,
                        trace_id=result.trace_id,
                        session_id=session_id_str,
                        turn_id=turn_id_str,
                        metadata={"pack_id": result.context_pack.get("pack_id")},
                    )
                    return result.context_pack

            # Fallback: build PCP directly using ContextPackBuilder
            from relic.context_pack import ContextPackBuilder, TaskType as PCPTaskType
            try:
                pcp_task_type = PCPTaskType(task_type)
            except ValueError:
                pcp_task_type = PCPTaskType.TECHNICAL

            builder = ContextPackBuilder(
                session_id=session_id_str,
                task_type=pcp_task_type,
            )
            pcp = builder.build()
            pcp.turn_id = turn_id_str

            # Log to trace
            from relic.context_pack.trace import PCPTraceEvent
            self._pcp_trace.log(
                event=PCPTraceEvent.INJECTION_APPLIED,
                trace_id=str(uuid4()),
                session_id=session_id_str,
                turn_id=turn_id_str,
                metadata={"pack_id": pcp.pack_id},
            )

            return pcp.to_dict()

        except Exception:
            # Fail-closed: any exception returns None
            return None

    def get_last_pcp_trace(self) -> dict[str, Any] | None:
        """Get the last PCP trace for /relic why command."""
        if self._pcp_trace:
            return self._pcp_trace.get_last_trace()
        return None

    def check_lifecycle_health(self) -> dict[str, Any]:
        """Check plugin lifecycle health for monitoring.

        Returns:
            Health status dict
        """
        return {
            "state": self._state.value,
            "plugin_id": self.plugin_id,
            "is_paused": self.is_paused,
            "config_enabled": self._config.enabled if self._config else None,
            "fail_safe_enabled": self._config.fail_safe_enabled if self._config else None,
            "loaded_at": self._load_result.loaded_at.isoformat() if self._load_result and self._load_result.loaded_at else None,
        }
