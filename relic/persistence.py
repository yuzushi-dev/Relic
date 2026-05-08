"""Memory persistence with privacy-preserving storage.

This module provides memory persistence capabilities with zero-knowledge
guarantees - raw private data is never persisted, only hashes and
privacy-verified content.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

try:
    import structlog
    logger = structlog.get_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)


class PrivacyLevel(Enum):
    """Privacy classification levels for memory blocks.

    S0: Hard violation - content must be rejected
    S1: Quarantine - content requires review before use
    S2: Warning - overpersonalization detected
    """
    S0_HARD_VIOLATION = "s0"
    S1_QUARANTINE = "s1"
    S2_WARNING = "s2"
    SAFE = "safe"


@dataclass
class MemoryBlock:
    """A privacy-scanned memory block ready for persistence.

    Only hashes and privacy-verified content may be stored.
    """
    block_id: str
    content_hash: str  # SHA-256 of content
    privacy_level: PrivacyLevel
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(cls, content: str, privacy_level: PrivacyLevel, block_id: str | None = None) -> MemoryBlock:
        """Create a new memory block with content hash."""
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        return cls(
            block_id=block_id or content_hash[:16],
            content_hash=content_hash,
            privacy_level=privacy_level,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for storage."""
        return {
            "block_id": self.block_id,
            "content_hash": self.content_hash,
            "privacy_level": self.privacy_level.value,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryBlock:
        """Deserialize from dictionary."""
        return cls(
            block_id=data["block_id"],
            content_hash=data["content_hash"],
            privacy_level=PrivacyLevel(data["privacy_level"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            metadata=data.get("metadata", {}),
        )


@dataclass
class PrivacyTrace:
    """Audit trail for privacy decisions.

    Stores hashes and policy outcomes only - never raw content.
    """
    trace_id: str
    stage: str  # e.g., "input_scan", "rehydration", "output_gate"
    content_hash: str  # SHA-256 of original content
    privacy_level: PrivacyLevel
    policy_applied: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    rehydration_context: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for privacy_trace.jsonl."""
        return {
            "trace_id": self.trace_id,
            "stage": self.stage,
            "content_hash": self.content_hash,
            "privacy_level": self.privacy_level.value,
            "policy_applied": self.policy_applied,
            "timestamp": self.timestamp.isoformat(),
            "rehydration_context": self.rehydration_context,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PrivacyTrace:
        """Deserialize from dictionary."""
        return cls(
            trace_id=data["trace_id"],
            stage=data["stage"],
            content_hash=data["content_hash"],
            privacy_level=PrivacyLevel(data["privacy_level"]),
            policy_applied=data["policy_applied"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            rehydration_context=data.get("rehydration_context"),
        )


class MemoryPersistence:
    """Privacy-preserving memory persistence layer.

    Guarantees:
    - Raw content is never persisted directly
    - All content is hashed before storage
    - Privacy decisions are audited in trace
    """

    def __init__(self, trace_path: Path | None = None):
        self._blocks: dict[str, MemoryBlock] = {}
        self._trace_path = trace_path or Path("privacy_trace.jsonl")
        self._trace_path.parent.mkdir(parents=True, exist_ok=True)

    def store(self, content: str, privacy_level: PrivacyLevel, metadata: dict[str, Any] | None = None) -> MemoryBlock:
        """Store a memory block with privacy classification.

        Only stores hash and metadata - never raw content.
        """
        block = MemoryBlock.create(content, privacy_level)
        if metadata:
            block.metadata = metadata

        self._blocks[block.block_id] = block

        # Create trace for storage
        trace = PrivacyTrace(
            trace_id=block.block_id,
            stage="store",
            content_hash=block.content_hash,
            privacy_level=block.privacy_level,
            policy_applied=f"default_policy_{block.privacy_level.value}",
        )
        self._append_trace(trace)

        logger.debug("memory_stored",
                    block_id=block.block_id,
                    privacy_level=privacy_level.value)

        return block

    def get(self, block_id: str) -> MemoryBlock | None:
        """Retrieve a memory block by ID."""
        return self._blocks.get(block_id)

    def verify_content(self, content: str, block_id: str) -> bool:
        """Verify content matches stored hash."""
        block = self._blocks.get(block_id)
        if not block:
            return False
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        return content_hash == block.content_hash

    def _append_trace(self, trace: PrivacyTrace) -> None:
        """Append privacy decision to trace log."""
        with open(self._trace_path, "a") as f:
            f.write(json.dumps(trace.to_dict()) + "\n")

    def append_trace_direct(self, trace: PrivacyTrace) -> None:
        """Append a privacy trace directly to the log."""
        self._append_trace(trace)

    def get_trace(self) -> list[PrivacyTrace]:
        """Load all privacy traces from log."""
        traces = []
        if not self._trace_path.exists():
            return traces

        with open(self._trace_path) as f:
            for line in f:
                if line.strip():
                    traces.append(PrivacyTrace.from_dict(json.loads(line)))
        return traces

    def clear_trace(self) -> None:
        """Clear the trace log (for testing)."""
        if self._trace_path.exists():
            self._trace_path.unlink()
        self._blocks.clear()
