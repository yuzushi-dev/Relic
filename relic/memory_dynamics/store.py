"""Memory dynamics store for persistence.

This module provides storage for memory dynamics events and traces.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from relic.memory_dynamics.types import MemoryDynamicsEvent
from relic.persistence import MemoryPersistence, PrivacyLevel


class MemoryDynamicsStore:
    """Store for memory dynamics events and traces."""

    def __init__(self, persistence: MemoryPersistence | None = None):
        self._persistence = persistence or MemoryPersistence()
        self._events: list[MemoryDynamicsEvent] = []

    def store_event(self, event: MemoryDynamicsEvent) -> None:
        """Store a memory dynamics event."""
        self._events.append(event)
        
        # Also store in persistence for trace
        self._persistence.store(
            json.dumps(event.to_dict()),
            PrivacyLevel.SAFE,
            metadata={"event_id": event.event_id, "mechanism": event.mechanism.value},
        )

    def get_events(
        self,
        mechanism: str | None = None,
        limit: int = 100,
    ) -> list[MemoryDynamicsEvent]:
        """Get memory dynamics events, optionally filtered by mechanism."""
        events = self._events
        if mechanism:
            events = [e for e in events if e.mechanism.value == mechanism]
        return events[-limit:]

    def get_event(self, event_id: str) -> MemoryDynamicsEvent | None:
        """Get a specific event by ID."""
        for event in self._events:
            if event.event_id == event_id:
                return event
        return None

    def get_trace(self) -> list[MemoryDynamicsEvent]:
        """Get all events as a trace."""
        return self._events.copy()

    def clear_events(self) -> None:
        """Clear all stored events."""
        self._events.clear()
