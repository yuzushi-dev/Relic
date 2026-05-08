"""Fail-safe registry for plugin failure handling.

This module implements fail-safe mechanisms that ensure:
- Plugin failure produces NO memory injection
- Guidance is blocked when fail-safe triggers
- All failures are auditable

Key guarantees:
- Fail-safe is fail-closed: if anything goes wrong, guidance is blocked
- No memory injection on plugin failure
- SOUL.md, MEMORY.md, USER.md are never mutated by plugin failure
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class FailSafeTrigger(str, Enum):
    """Reasons for fail-safe trigger."""
    PERMISSION_DENIED = "permission_denied"
    HOOK_ERROR = "hook_error"
    CONFIG_ERROR = "config_error"
    LOAD_FAILURE = "load_failure"
    TIMEOUT = "timeout"
    SECURITY_VIOLATION = "security_violation"
    UNKNOWN = "unknown"
    MEMORY_CONTEXT_ABUSE = "memory_context_abuse"
    MONOLITHIC_PROMPT_INJECTION = "monolithic_prompt_injection"
    PROVIDER_SWITCH_WITHOUT_PROFILE = "provider_switch_without_profile"
    SOUL_CONTEXT_ABUSE = "soul_context_abuse"


@dataclass
class FailSafeEvent:
    """Record of a fail-safe trigger event."""
    trigger: FailSafeTrigger
    reason: str
    id: UUID = field(default_factory=uuid4)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    trace_id: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class FailSafeResult:
    """Result of fail-safe check."""
    triggered: bool
    blocked: bool
    trigger_reason: str | None = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


class FailSafeRegistry:
    """Registry for fail-safe callbacks and state.

    This registry maintains fail-safe state and callbacks:
    - If fail-safe is triggered, guidance is blocked
    - All triggers are recorded for audit
    - Fail-safe state is cleared on explicit resume
    """

    def __init__(self, enabled: bool = True) -> None:
        self._enabled = enabled
        self._triggered = False
        self._events: list[FailSafeEvent] = []
        self._callbacks: list[Callable[[str], None]] = []

    @property
    def enabled(self) -> bool:
        """Check if fail-safe is enabled."""
        return self._enabled

    @property
    def is_triggered(self) -> bool:
        """Check if fail-safe has been triggered."""
        return self._triggered

    def register_hook(self, callback: Callable[[str], None]) -> None:
        """Register a callback to be called when fail-safe triggers.

        Args:
            callback: Function that takes reason string
        """
        self._callbacks.append(callback)

    def register_callback(self, callback: Callable[[str], None]) -> None:
        """Alias for register_hook for compatibility."""
        self.register_hook(callback)

    def trigger(
        self,
        reason: str,
        trigger: FailSafeTrigger = FailSafeTrigger.UNKNOWN,
        trace_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> FailSafeResult:
        """Trigger the fail-safe.

        When triggered:
        - Guidance is blocked
        - Event is recorded
        - Callbacks are notified

        Args:
            reason: Human-readable reason for trigger
            trigger: Type of trigger
            trace_id: Optional trace ID for correlation
            metadata: Optional metadata

        Returns:
            FailSafeResult with trigger status
        """
        if not self._enabled:
            return FailSafeResult(
                triggered=False,
                blocked=False,
                trigger_reason=None,
            )

        self._triggered = True

        event = FailSafeEvent(
            trigger=trigger,
            reason=reason,
            trace_id=trace_id,
            metadata=metadata,
        )
        self._events.append(event)

        # Notify callbacks
        for callback in self._callbacks:
            try:
                callback(reason)
            except Exception:
                # Callbacks should not raise - log and continue
                pass

        return FailSafeResult(
            triggered=True,
            blocked=True,
            trigger_reason=reason,
        )

    def check(self) -> FailSafeResult:
        """Check fail-safe status.

        Returns:
            FailSafeResult with current status
        """
        if not self._enabled:
            return FailSafeResult(
                triggered=False,
                blocked=False,
                trigger_reason=None,
            )

        if self._triggered:
            last_event = self._events[-1] if self._events else None
            return FailSafeResult(
                triggered=True,
                blocked=True,
                trigger_reason=last_event.reason if last_event else None,
            )

        return FailSafeResult(
            triggered=False,
            blocked=False,
            trigger_reason=None,
        )

    def reset(self) -> None:
        """Reset fail-safe state (only for testing/admin)."""
        self._triggered = False
        # Note: events are kept for audit trail

    def get_events(self) -> list[FailSafeEvent]:
        """Get all fail-safe events for audit."""
        return list(self._events)

    def clear_events(self) -> None:
        """Clear fail-safe events (for testing only)."""
        self._events = []

    def get_last_trigger_reason(self) -> str | None:
        """Get the reason for the last fail-safe trigger."""
        if self._events:
            return self._events[-1].reason
        return None


def create_fail_safe_disabled_result() -> FailSafeResult:
    """Create a result indicating fail-safe is disabled."""
    return FailSafeResult(
        triggered=False,
        blocked=False,
        trigger_reason=None,
    )


def create_fail_safe_blocked_result(reason: str) -> FailSafeResult:
    """Create a result indicating fail-safe blocked guidance."""
    return FailSafeResult(
        triggered=True,
        blocked=True,
        trigger_reason=reason,
    )
