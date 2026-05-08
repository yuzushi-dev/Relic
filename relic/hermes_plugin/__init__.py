"""Relic Hermes Plugin - Ephemeral runtime guidance integration.

This package provides the Hermes plugin interface for Relic:
- plugin: Main plugin class and lifecycle hooks
- commands: /relic commands (why, pause, resume)
- hooks: Pre/post tool call hooks for permission enforcement
- fail_safe: Fail-safe mechanisms for plugin failure scenarios
- tool_permissions: Tool permission matrix enforcement

Key guarantees:
- Plugin failure produces no memory injection
- Only ephemeral per-turn context (no persistent system prompt changes)
- SOUL.md, MEMORY.md, USER.md are never mutated
- /relic pause disables all runtime guidance
- pre_tool_call enforces TOOL_PERMISSION_MATRIX.md
- roleplay mode cannot trigger L2+ side-effect tools without approval
- All tool permission decisions are auditable with reason_code and policy_version
"""

from relic.hermes_plugin.commands import RelicCommands
from relic.hermes_plugin.fail_safe import FailSafeRegistry, FailSafeResult
from relic.hermes_plugin.hooks import HookEvent, HookManager, ToolCallContext
from relic.hermes_plugin.plugin import PluginConfig, RelicHermesPlugin
from relic.hermes_plugin.resume_hooks import (
    ResumeHookEvent,
    ResumeHookResult,
    check_pending_output_reconciliation,
    on_checkpoint_resume,
    on_hermes_session_resume,
)
from relic.hermes_plugin.tool_permissions import (
    PermissionResult,
    ToolCategory,
    ToolPermissionMatrix,
)

__version__ = "0.1.0"

__all__ = [
    # Plugin
    "RelicHermesPlugin",
    "PluginConfig",
    # Commands
    "RelicCommands",
    # Hooks
    "HookManager",
    "HookEvent",
    "ToolCallContext",
    # Resume hooks
    "ResumeHookEvent",
    "ResumeHookResult",
    "on_hermes_session_resume",
    "on_checkpoint_resume",
    "check_pending_output_reconciliation",
    # Fail-safe
    "FailSafeRegistry",
    "FailSafeResult",
    # Tool permissions
    "ToolPermissionMatrix",
    "ToolCategory",
    "PermissionResult",
]
