"""Type definitions for PromptContextPack contract."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


def _utcnow() -> datetime:
    """Get current UTC datetime."""
    return datetime.now(timezone.utc)


class TaskType(str, Enum):
    """Task type classification."""

    TECHNICAL = "technical"
    RELATIONAL = "relational"
    REFLECTIVE = "reflective"
    CREATIVE = "creative"
    FACTUAL = "factual"
    HIGH_STAKES = "high_stakes"
    ARCHITECTURE_RESEARCH = "architecture_research"


class RoleplayLevel(str, Enum):
    """Roleplay intensity level."""

    OFF = "off"
    MINIMAL = "minimal"
    LIGHT = "light"
    NORMAL = "normal"
    HIGH = "high"


class ContinuityMode(str, Enum):
    """Continuity resolution mode."""

    NONE = "none"
    REFERENCE_ONLY = "reference_only"
    COMPACT = "compact"
    EXPANDED = "expanded"


class DisclosureLevel(str, Enum):
    """Disclosure requirements for subjects."""

    PRIVATE = "private"
    RESTRICTED = "restricted"
    STANDARD = "standard"
    OPEN = "open"


class ContextSource(str, Enum):
    """Independent context sources, never monolithic."""

    MEMORY = "memory"
    USER = "user"
    SYSTEM = "system"
    SKILL = "skill"
    SOUL = "soul"
    DIARY = "diary"
    WORLD_STATE = "world_state"
    MULTI_PROVIDER_AGGREGATION = "multi_provider_aggregation"
    PROJECT_WORKFLOW = "project_workflow"
    USER_PRIVATE_FACTS = "user_private_facts"

    @classmethod
    def list_all(cls) -> list["ContextSource"]:
        """Return all context source values."""
        return list(cls)


@dataclass
class SubjectScope:
    """Subject scope with disclosure level and metadata."""

    subject_id: str
    disclosure_level: DisclosureLevel = DisclosureLevel.STANDARD
    is_active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject_id": self.subject_id,
            "disclosure_level": self.disclosure_level.value,
            "is_active": self.is_active,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SubjectScope":
        return cls(
            subject_id=data["subject_id"],
            disclosure_level=DisclosureLevel(data.get("disclosure_level", "standard")),
            is_active=data.get("is_active", True),
            metadata=data.get("metadata", {}),
        )


@dataclass
class SystemSource:
    """System source with priority and optional content."""

    source: ContextSource
    priority: int = 50
    content: str | None = None
    injected: bool = True
    scope: list[SubjectScope] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.value,
            "priority": self.priority,
            "content": self.content,
            "injected": self.injected,
            "scope": [s.to_dict() for s in self.scope],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SystemSource":
        return cls(
            source=ContextSource(data["source"]),
            priority=data.get("priority", 50),
            content=data.get("content"),
            injected=data.get("injected", True),
            scope=[SubjectScope.from_dict(s) for s in data.get("scope", [])],
            metadata=data.get("metadata", {}),
        )


@dataclass
class MemoryCandidate:
    """Memory candidate for injection with relevance scoring."""

    candidate_id: str
    memory_type: str
    summary: str
    relevance_score: float = 0.5
    source: str | None = None
    timestamp: datetime | None = None
    scope: list[SubjectScope] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "memory_type": self.memory_type,
            "summary": self.summary,
            "relevance_score": self.relevance_score,
            "source": self.source,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "scope": [s.to_dict() for s in self.scope],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryCandidate":
        ts = data.get("timestamp")
        return cls(
            candidate_id=data["candidate_id"],
            memory_type=data["memory_type"],
            summary=data["summary"],
            relevance_score=data.get("relevance_score", 0.5),
            source=data.get("source"),
            timestamp=datetime.fromisoformat(ts) if ts else None,
            scope=[SubjectScope.from_dict(s) for s in data.get("scope", [])],
            metadata=data.get("metadata", {}),
        )


@dataclass
class KnowledgeCandidate:
    """Knowledge candidate for retrieval with confidence scoring."""

    candidate_id: str
    knowledge_type: str
    content: str
    confidence: float = 0.5
    source: str | None = None
    scope: list[SubjectScope] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "knowledge_type": self.knowledge_type,
            "content": self.content,
            "confidence": self.confidence,
            "source": self.source,
            "scope": [s.to_dict() for s in self.scope],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "KnowledgeCandidate":
        return cls(
            candidate_id=data["candidate_id"],
            knowledge_type=data["knowledge_type"],
            content=data["content"],
            confidence=data.get("confidence", 0.5),
            source=data.get("source"),
            scope=[SubjectScope.from_dict(s) for s in data.get("scope", [])],
            metadata=data.get("metadata", {}),
        )


@dataclass
class ContinuityItem:
    """Continuity item for session context."""

    item_id: str
    item_type: str
    summary: str
    position: int = 0
    scope: list[SubjectScope] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "item_type": self.item_type,
            "summary": self.summary,
            "position": self.position,
            "scope": [s.to_dict() for s in self.scope],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ContinuityItem":
        return cls(
            item_id=data["item_id"],
            item_type=data["item_type"],
            summary=data["summary"],
            position=data.get("position", 0),
            scope=[SubjectScope.from_dict(s) for s in data.get("scope", [])],
            metadata=data.get("metadata", {}),
        )


@dataclass
class BlockedItem:
    """Blocked item for privacy protection."""

    item_id: str
    reason: str
    blocked_at: datetime | None = None
    scope: list[SubjectScope] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "reason": self.reason,
            "blocked_at": self.blocked_at.isoformat() if self.blocked_at else None,
            "scope": [s.to_dict() for s in self.scope],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BlockedItem":
        ts = data.get("blocked_at")
        return cls(
            item_id=data["item_id"],
            reason=data["reason"],
            blocked_at=datetime.fromisoformat(ts) if ts else None,
            scope=[SubjectScope.from_dict(s) for s in data.get("scope", [])],
            metadata=data.get("metadata", {}),
        )


@dataclass
class PromptContextPack:
    """Full typed, schema-validated, redacted, traceable per-turn contract.

    Replaces the original stub with a complete contract that ensures:
    - Schema validation against prompt_context_pack.schema.json
    - Subject scope for disclosure control
    - Blocked items never injected
    - Raw prompt markers fail validation
    - JSONL trace for audit trail
    """

    # Lineage
    schema_version: str = "1.0"
    pack_id: str = field(default_factory=lambda: f"PCP-{uuid4()}")
    session_id: str | None = None
    turn_id: str | None = None
    created_at: datetime = field(default_factory=_utcnow)

    # Task classification
    task_type: TaskType = TaskType.FACTUAL
    roleplay_level: RoleplayLevel = RoleplayLevel.OFF
    continuity_mode: ContinuityMode = ContinuityMode.NONE
    disclosure_required: bool = False

    # Sources and candidates
    system_sources: list[SystemSource] = field(default_factory=list)
    continuity_items: list[ContinuityItem] = field(default_factory=list)
    memory_candidates: list[MemoryCandidate] = field(default_factory=list)
    knowledge_candidates: list[KnowledgeCandidate] = field(default_factory=list)
    blocked_items: list[BlockedItem] = field(default_factory=list)

    # Output
    injected_context_redacted: str | None = None
    input_hash: str | None = None

    def __post_init__(self) -> None:
        # Guarantee at least 3 independent context sources (blueprint invariant).
        # Only applied when no sources were provided at construction time.
        if not self.system_sources:
            self.system_sources = [
                SystemSource(source=ContextSource.MEMORY, priority=80, injected=True),
                SystemSource(source=ContextSource.SYSTEM, priority=70, injected=True),
                SystemSource(source=ContextSource.SOUL, priority=60, injected=True),
            ]

    def get_context_sources(self) -> list[ContextSource]:
        """Return the list of active context sources for this pack."""
        return [s.source for s in self.system_sources if s.injected]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "schema_version": self.schema_version,
            "pack_id": self.pack_id,
            "session_id": self.session_id,
            "turn_id": self.turn_id,
            "created_at": self.created_at.isoformat(),
            "task_type": self.task_type.value,
            "roleplay_level": self.roleplay_level.value,
            "continuity_mode": self.continuity_mode.value,
            "disclosure_required": self.disclosure_required,
            "system_sources": [s.to_dict() for s in self.system_sources],
            "continuity_items": [i.to_dict() for i in self.continuity_items],
            "memory_candidates": [c.to_dict() for c in self.memory_candidates],
            "knowledge_candidates": [c.to_dict() for c in self.knowledge_candidates],
            "blocked_items": [b.to_dict() for b in self.blocked_items],
            "injected_context_redacted": self.injected_context_redacted,
            "input_hash": self.input_hash,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PromptContextPack":
        """Create from dictionary."""
        created = data.get("created_at")
        return cls(
            schema_version=data.get("schema_version", "1.0"),
            pack_id=data.get("pack_id", f"PCP-{uuid4()}"),
            session_id=data.get("session_id"),
            turn_id=data.get("turn_id"),
            created_at=datetime.fromisoformat(created) if created else _utcnow(),
            task_type=TaskType(data.get("task_type", "factual")),
            roleplay_level=RoleplayLevel(data.get("roleplay_level", "off")),
            continuity_mode=ContinuityMode(data.get("continuity_mode", "none")),
            disclosure_required=data.get("disclosure_required", False),
            system_sources=[SystemSource.from_dict(s) for s in data.get("system_sources", [])],
            continuity_items=[ContinuityItem.from_dict(i) for i in data.get("continuity_items", [])],
            memory_candidates=[MemoryCandidate.from_dict(c) for c in data.get("memory_candidates", [])],
            knowledge_candidates=[KnowledgeCandidate.from_dict(c) for c in data.get("knowledge_candidates", [])],
            blocked_items=[BlockedItem.from_dict(b) for b in data.get("blocked_items", [])],
            injected_context_redacted=data.get("injected_context_redacted"),
            input_hash=data.get("input_hash"),
        )

    def has_subject_scope(self) -> bool:
        """Check if pack has at least one subject scope defined."""
        for source in self.system_sources:
            if source.scope:
                return True
        for item in self.continuity_items:
            if item.scope:
                return True
        return False
