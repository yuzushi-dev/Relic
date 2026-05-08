"""Relic Hermes Plugin - Main plugin class and lifecycle.

This module implements the Hermes plugin interface for Relic.
The plugin provides ephemeral runtime guidance without modifying
persistent memory stores (SOUL.md, MEMORY.md, USER.md).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from relic.hermes_plugin.commands import RelicCommands
from relic.hermes_plugin.fail_safe import FailSafeRegistry
from relic.hermes_plugin.hooks import HookManager
from relic.hermes_plugin.tool_permissions import ToolPermissionMatrix

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
    - /relic why: Show last CAC trace
    - /relic pause: Disable runtime guidance
    - /relic resume: Re-enable runtime guidance
    - Pre-tool-call permission enforcement
    - Ephemeral context injection (no persistent changes)

    Guarantees:
    - Plugin failure produces NO memory injection
    - Only ephemeral per-turn context
    - Never mutates SOUL.md, MEMORY.md, USER.md
    - All tool permission decisions are auditable
    """

    def __init__(self) -> None:
        self._state = PluginState.UNLOADED
        self._config: PluginConfig | None = None
        self._commands: RelicCommands | None = None
        self._hooks: HookManager | None = None
        self._fail_safe: FailSafeRegistry | None = None
        self._tool_permissions: ToolPermissionMatrix | None = None
        self._load_result: PluginLoadResult | None = None
        # Cached pause controller (lazily initialized)
        self._pause_controller: PauseController | None = None
        # Cached CAC controller (lazily initialized)
        self._cac_controller: CACController | None = None

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
            matrix_path = self._config.tool_permission_matrix_path
            self._tool_permissions = ToolPermissionMatrix(
                matrix_path=matrix_path,
                policy_version=self._config.policy_version,
            )

            # Initialize hooks for pre/post tool call
            self._hooks = HookManager(
                permission_matrix=self._tool_permissions,
                fail_safe=self._fail_safe,
                roleplay_blocks_l2=self._config.roleplay_blocks_l2_tools,
            )

            # Initialize commands
            self._commands = RelicCommands(
                pause_controller=self._pause_controller,
                cac_controller=self._cac_controller,
            )

            # Mark as loaded
            self._state = PluginState.LOADED
            self._load_result = PluginLoadResult(
                success=True,
                state=self._state,
                loaded_at=datetime.utcnow(),
                plugin_id=str(uuid4()),
            )

            return self._load_result

        except Exception as e:
            self._state = PluginState.FAILED
            self._load_result = PluginLoadResult(
                success=False,
                state=self._state,
                error_message=str(e),
            )
            return self._load_result

    def unload(self) -> None:
        """Unload the plugin gracefully.

        This ensures no guidance is injected after unload.
        """
        if self._state == PluginState.SHUTDOWN:
            return

        # Clear any cached state
        self._pause_controller = None
        self._cac_controller = None

        # Mark as unloaded (not failed - clean unload)
        self._state = PluginState.UNLOADED

    def shutdown(self) -> None:
        """Shutdown the plugin completely.

        This is called when Hermes is shutting down.
        """
        self.unload()
        self._state = PluginState.SHUTDOWN

    def get_commands(self) -> RelicCommands | None:
        """Get the commands handler."""
        return self._commands

    def get_hooks(self) -> HookManager | None:
        """Get the hooks manager."""
        return self._hooks

    def get_tool_permission_matrix(self) -> ToolPermissionMatrix | None:
        """Get the tool permission matrix."""
        return self._tool_permissions

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

        Returns:
            Dict representation of last CAC trace, or None
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
        session_id: UUID | None = None,
    ) -> dict[str, Any] | None:
        """Inject ephemeral context for current turn.

        This returns context WITHOUT modifying persistent memory.
        Context is only valid for the current turn and is never
        written to SOUL.md, MEMORY.md, or USER.md.

        Args:
            session_id: Optional session ID

        Returns:
            Ephemeral context dict or None if paused/blocked
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

        # Return ephemeral context (no persistent store modification)
        return {
            "type": "ephemeral_guidance",
            "session_id": str(session_id) if session_id else None,
            "timestamp": datetime.utcnow().isoformat(),
            "policy_version": self._config.policy_version,
            "privacy_gateway_active": self._config.privacy_gateway_enabled,
        }

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
