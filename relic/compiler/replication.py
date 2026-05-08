"""Replication bundle generation for reproducibility verification.

This module provides replication bundle creation that enables:
- Verifiable reproduction of compilation outputs
- Independent verification of artifact checksums
- Cross-platform replication metadata
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from relic.compiler.lineage import LineageTracker
from relic.compiler.report import CompilerReport


@dataclass
class ReplicationMetadata:
    """Metadata for replication bundle."""
    bundle_id: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    compiler_version: str = "1.0.0"
    replication_factors: list[str] = field(default_factory=list)
    artifact_refs: list[str] = field(default_factory=list)
    source_snapshot_refs: list[str] = field(default_factory=list)
    checksum: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "bundle_id": self.bundle_id,
            "created_at": self.created_at.isoformat() + "Z",
            "compiler_version": self.compiler_version,
            "replication_factors": self.replication_factors,
            "artifact_refs": self.artifact_refs,
            "source_snapshot_refs": self.source_snapshot_refs,
            "checksum": self.checksum,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReplicationMetadata:
        """Deserialize from dictionary."""
        return cls(
            bundle_id=data["bundle_id"],
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
            compiler_version=data.get("compiler_version", "1.0.0"),
            replication_factors=data.get("replication_factors", []),
            artifact_refs=data.get("artifact_refs", []),
            source_snapshot_refs=data.get("source_snapshot_refs", []),
            checksum=data.get("checksum", ""),
            metadata=data.get("metadata", {}),
        )


class ReplicationBundle:
    """Bundle for replication and reproducibility.

    Contains all information needed to reproduce compilation
    outputs including lineage, reports, and checksums.
    """

    def __init__(self, bundle_id: str | None = None):
        self._bundle_id = bundle_id or self._generate_bundle_id()
        self._metadata = ReplicationMetadata(bundle_id=self._bundle_id)
        self._artifacts: dict[str, dict[str, Any]] = {}
        self._reports: dict[str, CompilerReport] = {}
        self._lineage_tracker = LineageTracker()

    @property
    def bundle_id(self) -> str:
        """Get bundle ID."""
        return self._bundle_id

    @property
    def metadata(self) -> ReplicationMetadata:
        """Get replication metadata."""
        return self._metadata

    def add_artifact(self, artifact_id: str, content: dict[str, Any]) -> None:
        """Add an artifact to the bundle."""
        self._artifacts[artifact_id] = content
        self._metadata.artifact_refs.append(artifact_id)

        # Register lineage if source info present
        source_id = content.get("source_snapshot_id", "")
        if source_id:
            self._lineage_tracker.register(
                artifact_id=artifact_id,
                source_snapshot_id=source_id,
                content=content,
                metadata={"bundle_id": self._bundle_id},
            )
            self._metadata.source_snapshot_refs.append(source_id)

    def add_report(self, report: CompilerReport) -> None:
        """Add a compiler report to the bundle."""
        self._reports[report.artifact_id] = report

    def verify_artifact_checksum(self, artifact_id: str, content: dict[str, Any]) -> bool:
        """Verify an artifact's checksum."""
        if artifact_id not in self._artifacts:
            return False

        # Get stored artifact
        stored = self._artifacts[artifact_id]
        stored_checksum = hashlib.sha256(
            json.dumps(stored, sort_keys=True).encode()
        ).hexdigest()

        # Compute new checksum
        new_checksum = hashlib.sha256(
            json.dumps(content, sort_keys=True).encode()
        ).hexdigest()

        return stored_checksum == new_checksum

    def verify_reproducibility(self, other_bundle: ReplicationBundle) -> bool:
        """Verify that another bundle produces the same outputs.

        Compares content checksums regardless of artifact IDs, so two
        compilations of the same data are considered reproducible even
        if their IDs differ (e.g., timestamp-based).
        """
        def _content_checksums(bundle: ReplicationBundle) -> set[str]:
            return {
                hashlib.sha256(
                    json.dumps(v, sort_keys=True).encode()
                ).hexdigest()
                for v in bundle._artifacts.values()
            }

        return _content_checksums(self) == _content_checksums(other_bundle)

    def compute_bundle_checksum(self) -> str:
        """Compute checksum for the entire bundle."""
        bundle_content = {
            "bundle_id": self._bundle_id,
            "artifacts": {
                k: hashlib.sha256(
                    json.dumps(v, sort_keys=True).encode()
                ).hexdigest()
                for k, v in self._artifacts.items()
            },
            "metadata": self._metadata.to_dict(),
        }
        return hashlib.sha256(
            json.dumps(bundle_content, sort_keys=True).encode()
        ).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """Serialize bundle to dictionary."""
        # Update metadata checksum
        self._metadata.checksum = self.compute_bundle_checksum()

        return {
            "metadata": self._metadata.to_dict(),
            "artifacts": self._artifacts,
            "reports": {
                k: v.to_dict() for k, v in self._reports.items()
            },
            "lineage": [lin.to_dict() for lin in self._lineage_tracker.get_all()],
        }

    def to_json(self, indent: int | None = 2) -> str:
        """Serialize bundle to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def save(self, path: Path | str) -> None:
        """Save bundle to file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            f.write(self.to_json())

    @classmethod
    def load(cls, path: Path | str) -> ReplicationBundle:
        """Load bundle from file."""
        path = Path(path)
        with open(path) as f:
            data = json.load(f)

        bundle = cls(bundle_id=data["metadata"]["bundle_id"])

        for artifact_id, content in data.get("artifacts", {}).items():
            bundle.add_artifact(artifact_id, content)

        for report_id, report_data in data.get("reports", {}).items():
            bundle.add_report(CompilerReport.from_dict(report_data))

        return bundle

    def _generate_bundle_id(self) -> str:
        """Generate a unique bundle ID."""
        timestamp = datetime.utcnow().isoformat()
        return hashlib.sha256(timestamp.encode()).hexdigest()[:32]

    def get_artifact(self, artifact_id: str) -> dict[str, Any] | None:
        """Get an artifact from the bundle."""
        return self._artifacts.get(artifact_id)

    def get_report(self, artifact_id: str) -> CompilerReport | None:
        """Get a report from the bundle."""
        return self._reports.get(artifact_id)

    def list_artifact_ids(self) -> list[str]:
        """List all artifact IDs in the bundle."""
        return list(self._artifacts.keys())
