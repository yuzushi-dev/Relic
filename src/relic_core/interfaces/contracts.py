"""Minimal runtime contracts frozen from current migration evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@dataclass(slots=True)
class SessionMessage:
    """Normalized transcript unit consumed by Relic extractors."""

    role: str
    content: str
    session_id: str
    session_key: str | None = None
    timestamp: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SessionRecord:
    """Opaque transcript handle with enough metadata for runtime filtering."""

    session_id: str
    updated_at: datetime
    state_key: str
    session_key: str | None = None
    size_bytes: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class MessageSource(Protocol):
    def load_messages(self) -> list[dict[str, Any]]:
        """Return inbound message records suitable for extraction."""


@runtime_checkable
class SessionSource(Protocol):
    def list_recent_sessions(self, *, since: datetime | None = None) -> list[SessionRecord]:
        """Return transcript handles ordered by recency."""

    def load_transcript(self, session: SessionRecord | str) -> list[SessionMessage]:
        """Return a normalized transcript for one session handle."""


@runtime_checkable
class DeliverySink(Protocol):
    def deliver_text(self, target: str, content: str) -> None:
        """Deliver a bounded text artifact or check-in to a runtime target."""


@runtime_checkable
class SchedulerBinding(Protocol):
    def jobs_location(self) -> Path:
        """Return the storage location that defines the scheduler job state."""


@runtime_checkable
class ModelBackend(Protocol):
    def complete(self, prompt: str, *, model: str | None = None) -> str:
        """Run one model completion for a normalized prompt."""


@runtime_checkable
class ArtifactPublisher(Protocol):
    def publish(self, artifact_name: str, content: str) -> Path:
        """Persist one generated artifact and return its final path."""


@runtime_checkable
class ArtifactGate(Protocol):
    def is_allowed(self, artifact_name: str) -> bool:
        """Return True when an artifact may cross the runtime boundary."""
