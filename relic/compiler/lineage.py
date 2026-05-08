"""Artifact lineage tracking for zero-knowledge compilation.

This module provides lineage tracking that:
- Associates artifacts with their source snapshots
- Maintains cryptographic checksums for verification
- Enables reproducibility verification
- Supports audit trail generation
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ArtifactLineage:
    """Immutable lineage record for an artifact.

    Tracks the complete provenance chain from source to compiled output.
    """
    artifact_id: str
    source_snapshot_id: str
    checksum: str  # SHA-256 of artifact content
    parent_lineage_refs: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize lineage to dictionary."""
        return {
            "artifact_id": self.artifact_id,
            "source_snapshot_id": self.source_snapshot_id,
            "checksum": self.checksum,
            "parent_lineage_refs": self.parent_lineage_refs,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ArtifactLineage:
        """Deserialize lineage from dictionary."""
        return cls(
            artifact_id=data["artifact_id"],
            source_snapshot_id=data["source_snapshot_id"],
            checksum=data["checksum"],
            parent_lineage_refs=data.get("parent_lineage_refs", []),
            created_at=datetime.fromisoformat(data["created_at"]),
            metadata=data.get("metadata", {}),
        )

    @staticmethod
    def compute_checksum(content: str | dict[str, Any]) -> str:
        """Compute SHA-256 checksum for content."""
        if isinstance(content, dict):
            content = json.dumps(content, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()


class LineageTracker:
    """Tracks lineage for all compiled artifacts.

    Provides a registry for artifact lineage records and
    methods for verifying reproducibility.
    """

    def __init__(self):
        self._lineages: dict[str, ArtifactLineage] = {}

    def register(
        self,
        artifact_id: str,
        source_snapshot_id: str,
        content: str | dict[str, Any],
        parent_refs: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ArtifactLineage:
        """Register a new artifact lineage."""
        lineage = ArtifactLineage(
            artifact_id=artifact_id,
            source_snapshot_id=source_snapshot_id,
            checksum=self.compute_checksum(content),
            parent_lineage_refs=parent_refs or [],
            metadata=metadata or {},
        )
        self._lineages[artifact_id] = lineage
        return lineage

    def get(self, artifact_id: str) -> ArtifactLineage | None:
        """Get lineage for an artifact."""
        return self._lineages.get(artifact_id)

    def verify(self, artifact_id: str, content: str | dict[str, Any]) -> bool:
        """Verify content matches stored checksum."""
        lineage = self._lineages.get(artifact_id)
        if not lineage:
            return False
        return lineage.checksum == self.compute_checksum(content)

    def get_all(self) -> list[ArtifactLineage]:
        """Get all registered lineages."""
        return list(self._lineages.values())

    def compute_checksum(self, content: str | dict[str, Any]) -> str:
        """Compute SHA-256 checksum."""
        return ArtifactLineage.compute_checksum(content)
