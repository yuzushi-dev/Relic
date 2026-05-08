"""Relic commands for Hermes - /relic why, /relic pause, /relic resume.

This module implements the command handlers for the Relic plugin.
Commands are ephemeral operations that don't modify persistent memory.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import UUID

if TYPE_CHECKING:
    from relic.cac.controller import CACController
    from relic.control.pause import PauseController


class RelicCommand(str, Enum):
    """Available /relic commands."""
    WHY = "why"
    PAUSE = "pause"
    RESUME = "resume"
    STATUS = "status"


@dataclass
class CommandResult:
    """Result of a command execution."""
    command: RelicCommand
    success: bool
    message: str
    data: dict[str, Any] | None = None
    executed_at: datetime | None = None


@dataclass
class WhyResult:
    """Result of /relic why command."""
    trace_id: str | None = None
    memory_id: str | None = None
    decision: str | None = None
    severity: str | None = None
    skip_reason: str | None = None
    timestamp: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class PauseResult:
    """Result of /relic pause command."""
    success: bool = False
    paused: bool = False
    message: str = ""
    session_id: str | None = None


@dataclass
class StatusResult:
    """Result of /relic status command."""
    plugin_loaded: bool = False
    guidance_paused: bool = False
    last_trace_available: bool = False
    policy_version: str = "1.0.0"
    session_id: str | None = None


class RelicCommands:
    """Handler for /relic commands.

    All commands are:
    - Ephemeral (no persistent memory modification)
    - Audit logged
    - Fail-safe (fail closed on errors)
    """

    def __init__(
        self,
        pause_controller: PauseController | None = None,
        cac_controller: CACController | None = None,
    ) -> None:
        self._pause_controller = pause_controller
        self._cac_controller = cac_controller

    def execute(
        self,
        command: RelicCommand,
        session_id: UUID | None = None,
        **kwargs: Any,
    ) -> CommandResult:
        """Execute a /relic command.

        Args:
            command: The command to execute
            session_id: Optional session ID
            **kwargs: Additional command arguments

        Returns:
            CommandResult with execution status
        """
        try:
            if command == RelicCommand.WHY:
                return self._execute_why(session_id)
            elif command == RelicCommand.PAUSE:
                return self._execute_pause(session_id)
            elif command == RelicCommand.RESUME:
                return self._execute_resume(session_id)
            elif command == RelicCommand.STATUS:
                return self._execute_status(session_id)
            else:
                return CommandResult(
                    command=command,
                    success=False,
                    message=f"Unknown command: {command}",
                )
        except Exception as e:
            return CommandResult(
                command=command,
                success=False,
                message=f"Command failed: {str(e)}",
            )

    def _execute_why(self, session_id: UUID | None) -> CommandResult:
        """Execute /relic why - show last CAC trace.

        This returns information about the last CAC decision
        without exposing raw memory content.
        """
        try:
            if not self._cac_controller:
                return CommandResult(
                    command=RelicCommand.WHY,
                    success=False,
                    message="CAC controller not available",
                )

            traces = self._cac_controller.get_traces()

            if not traces:
                return CommandResult(
                    command=RelicCommand.WHY,
                    success=True,
                    message="No CAC traces available",
                    data={"traces": []},
                )

            last_trace = traces[-1]

            why_result = WhyResult(
                trace_id=last_trace.trace_id,
                memory_id=last_trace.memory_id,
                decision=last_trace.decision,
                severity=last_trace.severity,
                skip_reason=last_trace.skip_reason,
                timestamp=getattr(last_trace, 'timestamp', None),
                metadata=last_trace.metadata or {},
            )
            if why_result.timestamp and hasattr(why_result.timestamp, 'isoformat'):
                why_result.timestamp = why_result.timestamp.isoformat()

            return CommandResult(
                command=RelicCommand.WHY,
                success=True,
                message="Last CAC trace retrieved",
                data={
                    "trace": {
                        "trace_id": why_result.trace_id,
                        "memory_id": why_result.memory_id,
                        "decision": why_result.decision,
                        "severity": why_result.severity,
                        "skip_reason": why_result.skip_reason,
                        "timestamp": why_result.timestamp,
                        # Note: metadata may contain factors but NOT raw content
                        "factors": why_result.metadata.get("factors") if why_result.metadata else None,
                        "confidence": why_result.metadata.get("confidence") if why_result.metadata else None,
                    }
                },
            )

        except Exception as e:
            return CommandResult(
                command=RelicCommand.WHY,
                success=False,
                message=f"Failed to get CAC trace: {str(e)}",
            )

    def _execute_pause(self, session_id: UUID | None) -> CommandResult:
        """Execute /relic pause - disable runtime guidance.

        When paused, all runtime guidance is disabled until resume.
        """
        try:
            if not self._pause_controller:
                return CommandResult(
                    command=RelicCommand.PAUSE,
                    success=False,
                    message="Pause controller not available",
                )

            self._pause_controller.pause(
                session_id=session_id,
                reason="user_initiated",
            )

            return CommandResult(
                command=RelicCommand.PAUSE,
                success=True,
                message="Runtime guidance paused",
                data={
                    "paused": True,
                    "session_id": str(session_id) if session_id else None,
                },
            )

        except Exception as e:
            return CommandResult(
                command=RelicCommand.PAUSE,
                success=False,
                message=f"Failed to pause: {str(e)}",
            )

    def _execute_resume(self, session_id: UUID | None) -> CommandResult:
        """Execute /relic resume - re-enable runtime guidance."""
        try:
            if not self._pause_controller:
                return CommandResult(
                    command=RelicCommand.RESUME,
                    success=False,
                    message="Pause controller not available",
                )

            self._pause_controller.resume(session_id=session_id)

            return CommandResult(
                command=RelicCommand.RESUME,
                success=True,
                message="Runtime guidance resumed",
                data={
                    "paused": False,
                    "session_id": str(session_id) if session_id else None,
                },
            )

        except Exception as e:
            return CommandResult(
                command=RelicCommand.RESUME,
                success=False,
                message=f"Failed to resume: {str(e)}",
            )

    def _execute_status(self, session_id: UUID | None) -> CommandResult:
        """Execute /relic status - show plugin status."""
        try:
            is_paused = False
            if self._pause_controller:
                is_paused = self._pause_controller.is_paused(session_id)

            has_traces = False
            if self._cac_controller:
                traces = self._cac_controller.get_traces()
                has_traces = len(traces) > 0

            return CommandResult(
                command=RelicCommand.STATUS,
                success=True,
                message="Plugin status retrieved",
                data={
                    "plugin_loaded": True,  # If we have this object, plugin is loaded
                    "guidance_paused": is_paused,
                    "last_trace_available": has_traces,
                    "policy_version": "1.0.0",  # Default policy version
                    "session_id": str(session_id) if session_id else None,
                },
            )

        except Exception as e:
            return CommandResult(
                command=RelicCommand.STATUS,
                success=False,
                message=f"Failed to get status: {str(e)}",
            )

    def set_pause_controller(self, controller: PauseController) -> None:
        """Set the pause controller (for lazy initialization)."""
        self._pause_controller = controller

    def set_cac_controller(self, controller: CACController) -> None:
        """Set the CAC controller (for lazy initialization)."""
        self._cac_controller = controller
