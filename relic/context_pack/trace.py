"""PCP trace module for redacted tracing of PromptContextPack construction.

All traces are redacted - never include raw content, prompts, or private data.
Traces record only:
- Event types (enum)
- Trace IDs (UUID)
- Session/turn IDs
- Metadata (category labels, decision outcomes, relevance scores)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
import re


class PCPTraceEvent(str, Enum):
    """PCP construction and injection events."""
    BUILD_STARTED = "build_started"
    BUILD_COMPLETED = "build_completed"
    BUILD_FAILED = "build_failed"
    INJECTION_REQUESTED = "injection_requested"
    INJECTION_APPLIED = "injection_applied"
    INJECTION_SKIPPED = "injection_skipped"
    FAIL_CLOSED = "fail_closed"
    FAIL_SAFE_TRIGGERED = "fail_safe_triggered"


@dataclass
class PCPTraceEntry:
    """A single trace entry - never contains raw content."""
    trace_id: str
    event: PCPTraceEvent
    timestamp: datetime = field(default_factory=datetime.utcnow)
    session_id: str | None = None
    turn_id: str | None = None
    # Metadata is sanitized - category labels, not raw content
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "event": self.event.value,
            "timestamp": self.timestamp.isoformat(),
            "session_id": self.session_id,
            "turn_id": self.turn_id,
            "metadata": self.metadata,
        }


class PCPTrace:
    """Redacted trace for PCP construction and injection.

    Guarantees:
    - No raw content in traces
    - No raw prompts stored
    - No private data recorded
    - Only trace IDs, event types, and sanitized metadata
    """

    # Patterns that indicate raw content that should be redacted
    _EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
    _SSN_PATTERN = re.compile(r'\b\d{3}-\d{2}-\d{4}\b')
    _PHONE_PATTERN = re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b')

    def __init__(self) -> None:
        self._entries: list[PCPTraceEntry] = []

    def log(
        self,
        event: PCPTraceEvent,
        trace_id: str,
        session_id: str | None = None,
        turn_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Log a trace entry (redacted)."""
        entry = PCPTraceEntry(
            trace_id=trace_id,
            event=event,
            session_id=session_id,
            turn_id=turn_id,
            metadata=self._sanitize_metadata(metadata) if metadata else None,
        )
        self._entries.append(entry)

    def _sanitize_metadata(self, metadata: dict[str, Any]) -> dict[str, Any]:
        """Sanitize metadata - remove any raw content."""
        sanitized = {}
        for key, value in metadata.items():
            if isinstance(value, str):
                # Redact strings that look like raw content
                sanitized[key] = self._redact_if_raw_content(value)
            elif isinstance(value, (int, float, bool)):
                sanitized[key] = value
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_metadata(value)
            elif isinstance(value, list):
                sanitized[key] = [self._redact_if_raw_content(str(v)) for v in value]
            else:
                sanitized[key] = str(value) if value is not None else None
        return sanitized

    def _redact_if_raw_content(self, value: str) -> str:
        """Check if a string looks like raw content and redact if so."""
        if not isinstance(value, str):
            return value

        # Check for private data patterns first (always redact)
        if self._EMAIL_PATTERN.search(value):
            return "[REDACTED]"
        if self._SSN_PATTERN.search(value):
            return "[REDACTED]"
        if self._PHONE_PATTERN.search(value):
            return "[REDACTED]"

        # Check for other raw content heuristics
        if self._looks_like_raw_content(value):
            return "[REDACTED]"

        return value

    def _looks_like_raw_content(self, value: str) -> bool:
        """Heuristic to detect raw content that should not be traced."""
        if not isinstance(value, str):
            return False

        # Check for common patterns indicating raw content
        raw_indicators = [
            len(value) > 100,  # Strings over 100 chars likely raw
            "\n" in value and len(value) > 50,  # Multi-line likely raw
            value.startswith("You ") or value.startswith("I ") or value.startswith("Gumi "),
            value.startswith("The user ") or value.startswith("User said"),
            # Code-like patterns
            ("def " in value and ":" in value) or ("function " in value and "{" in value),
            # Markdown patterns
            (value.startswith("# ") or value.startswith("## ") or value.startswith("**")),
        ]
        return any(raw_indicators)

    def get_trace(self) -> list[dict[str, Any]]:
        """Get all trace entries as dicts."""
        return [entry.to_dict() for entry in self._entries]

    def get_last_trace(self) -> dict[str, Any] | None:
        """Get the last trace entry for /relic why command."""
        if self._entries:
            return self._entries[-1].to_dict()
        return None

    def get_traces_by_event(self, event: PCPTraceEvent) -> list[PCPTraceEntry]:
        """Get all traces for a specific event."""
        return [e for e in self._entries if e.event == event]

    def clear(self) -> None:
        """Clear all traces (for testing)."""
        self._entries.clear()

    def get_count(self) -> int:
        """Get the number of trace entries."""
        return len(self._entries)


# Aliases for backwards compatibility
TraceWriter = PCPTrace


class NoOpTraceWriter:
    """No-op trace writer that does nothing.
    
    Use this when tracing is disabled.
    """

    def __init__(self) -> None:
        pass

    def log(
        self,
        event: PCPTraceEvent,
        trace_id: str,
        session_id: str | None = None,
        turn_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """No-op - does nothing."""
        pass

    def get_trace(self) -> list[dict[str, Any]]:
        """Returns empty list."""
        return []

    def get_last_trace(self) -> dict[str, Any] | None:
        """Returns None."""
        return None

    def get_traces_by_event(self, event: PCPTraceEvent) -> list[PCPTraceEntry]:
        """Returns empty list."""
        return []

    def clear(self) -> None:
        """No-op."""
        pass

    def get_count(self) -> int:
        """Returns 0."""
        return 0
