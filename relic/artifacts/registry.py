"""Artifact registry for managing Relic runtime artifacts.

The registry provides a centralized interface for:
- Registering new artifacts with lineage tracking
- Verifying artifact integrity via checksums
- Enforcing emission requirements (correction_cutoff, lineage_refs)
- Querying artifacts by type, lineage, or metadata

Privacy: The registry never stores raw content - only hashes and metadata.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from relic.artifacts.checksums import compute_checksum, verify_checksum
from relic.artifacts.types import (
    Artifact,
    ArtifactType,
    CorrectionCutoff,
    LineageRef,
    RuntimeProfilePack,
    SchemaVersion,
)


class ArtifactRegistry:
    """Registry for managing Relic runtime artifacts.

    The registry maintains an index of all artifacts with their metadata,
    checksums, and lineage relationships. Raw content is never stored.
    """

    def __init__(self, storage_path: Path | None = None) -> None:
        """Initialize the artifact registry.

        Args:
            storage_path: Optional path to artifact storage directory.
                         If None, uses in-memory storage.
        """
        self._storage_path = storage_path
        self._artifacts: dict[UUID, dict[str, Any]] = {}
        self._by_type: dict[ArtifactType, list[UUID]] = {}
        self._by_lineage: dict[UUID, list[UUID]] = {}

        if storage_path and storage_path.exists():
            self._load_index()

    def register(
        self,
        artifact: Artifact | RuntimeProfilePack,
        content: dict[str, Any] | None = None,
    ) -> tuple[bool, str]:
        """Register an artifact with the registry.

        Args:
            artifact: Artifact to register
            content: Optional content dict for checksum verification

        Returns:
            Tuple of (success, message)
        """
        # Check emission requirements
        can_emit, reason = artifact.can_emit()
        if not can_emit:
            return False, f"Cannot emit artifact: {reason}"

        artifact_id = artifact.id

        # Store artifact metadata
        artifact_dict = artifact.model_dump(mode="json")
        self._artifacts[artifact_id] = artifact_dict

        # Update type index
        artifact_type = ArtifactType(artifact.artifact_type)
        if artifact_type not in self._by_type:
            self._by_type[artifact_type] = []
        self._by_type[artifact_type].append(artifact_id)

        # Update lineage index
        for lineage_ref in artifact.lineage_refs:
            parent_id = lineage_ref.artifact_id
            if parent_id not in self._by_lineage:
                self._by_lineage[parent_id] = []
            self._by_lineage[parent_id].append(artifact_id)

        # Persist if storage path is configured
        if self._storage_path:
            self._save_artifact(artifact_dict)

        return True, f"Artifact {artifact_id} registered successfully"

    def _load_index(self) -> None:
        """Load registry index from storage."""
        index_path = self._storage_path / "registry_index.json"
        if not index_path.exists():
            return

        try:
            with open(index_path) as f:
                data = json.load(f)
                self._artifacts = {UUID(k): v for k, v in data.get("artifacts", {}).items()}
                self._by_type = {
                    ArtifactType(k): [UUID(x) for x in v]
                    for k, v in data.get("by_type", {}).items()
                }
                self._by_lineage = {
                    UUID(k): [UUID(x) for x in v]
                    for k, v in data.get("by_lineage", {}).items()
                }
        except Exception:
            pass

    def _save_artifact(self, artifact_dict: dict[str, Any]) -> None:
        """Save artifact to storage and update index."""
        if not self._storage_path:
            return

        self._storage_path.mkdir(parents=True, exist_ok=True)

        artifact_id = UUID(artifact_dict["id"])
        artifact_path = self._storage_path / f"{artifact_id}.json"
        with open(artifact_path, "w") as f:
            json.dump(artifact_dict, f, indent=2, default=str)

        # Update index
        index_path = self._storage_path / "registry_index.json"
        with open(index_path, "w") as f:
            json.dump(
                {
                    "artifacts": {str(k): v for k, v in self._artifacts.items()},
                    "by_type": {k.value: [str(x) for x in v] for k, v in self._by_type.items()},
                    "by_lineage": {str(k): [str(x) for x in v] for k, v in self._by_lineage.items()},
                },
                f,
                indent=2,
            )

    def get(self, artifact_id: UUID) -> dict[str, Any] | None:
        """Get artifact metadata by ID.

        Args:
            artifact_id: UUID of artifact to retrieve

        Returns:
            Artifact dict or None if not found
        """
        return self._artifacts.get(artifact_id)

    def get_by_type(self, artifact_type: ArtifactType) -> list[dict[str, Any]]:
        """Get all artifacts of a given type.

        Args:
            artifact_type: Type of artifacts to retrieve

        Returns:
            List of artifact dicts
        """
        artifact_ids = self._by_type.get(artifact_type, [])
        return [self._artifacts[aid] for aid in artifact_ids if aid in self._artifacts]

    def get_descendants(self, artifact_id: UUID) -> list[dict[str, Any]]:
        """Get all artifacts derived from the given artifact.

        Args:
            artifact_id: UUID of ancestor artifact

        Returns:
            List of descendant artifact dicts
        """
        descendant_ids = self._by_lineage.get(artifact_id, [])
        return [self._artifacts[did] for did in descendant_ids if did in self._artifacts]

    def verify_integrity(self, artifact_id: UUID) -> tuple[bool, str]:
        """Verify artifact integrity via checksum.

        Args:
            artifact_id: UUID of artifact to verify

        Returns:
            Tuple of (is_valid, message)
        """
        artifact_dict = self._artifacts.get(artifact_id)
        if not artifact_dict:
            return False, f"Artifact {artifact_id} not found"

        # Verify checksum
        stored_checksum = artifact_dict.get("checksum")
        if not stored_checksum:
            return False, f"Artifact {artifact_id} has no checksum"

        # Load full content if stored separately
        if self._storage_path:
            artifact_path = self._storage_path / f"{artifact_id}.json"
            if artifact_path.exists():
                with open(artifact_path) as f:
                    full_content = json.load(f)
            else:
                full_content = artifact_dict
        else:
            full_content = artifact_dict

        # Compute expected checksum
        content_for_check = {k: v for k, v in full_content.items() if k != "checksum"}
        if verify_checksum(content_for_check, stored_checksum):
            return True, f"Artifact {artifact_id} checksum verified"
        return False, f"Artifact {artifact_id} checksum mismatch"

    def create_runtime_profile(
        self,
        session_id: UUID,
        source_snapshot_id: UUID,
        prompt_hash: str,
        agent_id: str,
        agent_version: str,
        hint_hashes: list[str],
        profile_type: str = "session",
        lineage_refs: list[LineageRef] | None = None,
        corrections_applied: list[UUID] | None = None,
    ) -> tuple[RuntimeProfilePack | None, str]:
        """Create and register a runtime profile pack.

        Args:
            session_id: Session identifier
            source_snapshot_id: Source snapshot reference
            prompt_hash: Hash of prompt content
            agent_id: Agent identifier
            agent_version: Agent version
            hint_hashes: List of hint content hashes
            profile_type: Type of profile
            lineage_refs: Optional parent artifacts
            corrections_applied: Optional list of applied correction IDs

        Returns:
            Tuple of (RuntimeProfilePack or None, message)
        """
        now = datetime.utcnow()

        # Create correction cutoff
        correction_cutoff = CorrectionCutoff(
            cutoff_timestamp=now,
            corrections_applied=corrections_applied or [],
            corrections_pending=[],
            verified=True,
        )

        # Build runtime profile
        profile = RuntimeProfilePack(
            id=uuid4(),
            schema_version=SchemaVersion.current(),
            checksum="",  # Will be computed
            source_snapshot_id=source_snapshot_id,
            lineage_refs=lineage_refs or [],
            correction_cutoff=correction_cutoff,
            session_id=session_id,
            profile_type=profile_type,
            prompt_hash=prompt_hash,
            prompt_length=0,  # Cannot store actual length without content
            is_redacted=False,
            hint_hashes=hint_hashes,
            disputed_hints_excluded=0,
            sensitive_hints_downgraded=0,
            agent_id=agent_id,
            agent_version=agent_version,
            created_at=now,
        )

        # Compute checksum
        content = profile.model_dump(exclude={"checksum"})
        profile.checksum = compute_checksum(content)

        # Register
        success, msg = self.register(profile)
        if success:
            return profile, msg
        return None, msg

    def list_artifacts(
        self,
        artifact_type: ArtifactType | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """List artifacts with optional type filter.

        Args:
            artifact_type: Optional type filter
            limit: Maximum number of results

        Returns:
            List of artifact dicts
        """
        if artifact_type:
            ids = self._by_type.get(artifact_type, [])
        else:
            ids = list(self._artifacts.keys())

        return [
            self._artifacts[aid]
            for aid in ids[-limit:]
            if aid in self._artifacts
        ]
