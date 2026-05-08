"""Type definitions for Relic runtime artifacts.

This module defines the core artifact types for zero-knowledge runtime
profiles. All artifacts MUST include:
- schema_version: for contract compatibility
- checksum: for integrity verification
- lineage_refs: for audit trail and reproducibility
- correction_cutoff: for ensuring corrections are applied before emission

Privacy guarantees:
- RuntimeProfilePack contains NO raw session text
- Only content hashes and metadata are stored
- Disputed/sensitive hints are excluded or downgraded by policy
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class ArtifactType(str, Enum):
    """Enumeration of supported artifact types."""

    RUNTIME_PROFILE = "runtime_profile"
    AGENT_EMBODIMENT = "agent_embodiment"
    INTERACTION_POLICY = "interaction_policy"


class SchemaVersion(BaseModel):
    """Schema version metadata for contract compatibility."""

    major: int = Field(ge=0, description="Major version number")
    minor: int = Field(ge=0, description="Minor version number")
    patch: int = Field(ge=0, description="Patch version number")
    schema_uri: str = Field(description="URI to schema definition")

    @classmethod
    def current(cls) -> SchemaVersion:
        """Return the current schema version for this module."""
        return cls(
            major=1,
            minor=0,
            patch=0,
            schema_uri="https://relic-oss.dev/schemas/runtime_profile_pack/v1",
        )

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


class SourceSnapshotRef(BaseModel):
    """Reference to a source snapshot for artifact lineage.

    This provides provenance tracking without duplicating data.
    """

    snapshot_id: UUID = Field(default_factory=uuid4, description="Unique snapshot identifier")
    snapshot_type: str = Field(description="Type of snapshot (e.g., 'session', 'prompt')")
    content_hash: str = Field(description="SHA-256 hash of snapshot content")
    captured_at: datetime = Field(default_factory=datetime.utcnow)


class LineageRef(BaseModel):
    """Reference to a parent artifact for lineage tracking."""

    artifact_id: UUID = Field(description="Parent artifact UUID")
    artifact_type: ArtifactType = Field(description="Type of parent artifact")
    relationship: str = Field(description="Relationship type (e.g., 'derived_from', 'supersedes')")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CorrectionCutoff(BaseModel):
    """Correction cutoff metadata ensuring corrections are applied.

    This is a REQUIRED field for all artifacts. An artifact cannot be
    emitted without a valid correction_cutoff timestamp.
    """

    cutoff_timestamp: datetime = Field(
        description="All corrections up to this timestamp must be applied"
    )
    corrections_applied: list[UUID] = Field(
        default_factory=list,
        description="List of correction IDs that were applied",
    )
    corrections_pending: list[UUID] = Field(
        default_factory=list,
        description="List of correction IDs that are still pending",
    )
    verified: bool = Field(default=False, description="Whether cutoff has been verified")


class Artifact(BaseModel):
    """Base artifact type with required zero-knowledge fields.

    All artifact types inherit these mandatory fields:
    - schema_version: Contract compatibility
    - checksum: Integrity verification
    - source_snapshot_id: Provenance reference
    - lineage_refs: Audit trail
    - correction_cutoff: Correction enforcement
    """

    id: UUID = Field(default_factory=uuid4, description="Unique artifact identifier")
    artifact_type: ArtifactType = Field(description="Type of artifact")
    schema_version: SchemaVersion = Field(default_factory=SchemaVersion.current)
    checksum: str = Field(description="SHA-256 checksum of artifact content")
    source_snapshot_id: UUID | None = Field(
        default=None,
        description="Reference to source snapshot (REQUIRED for emission)",
    )
    lineage_refs: list[LineageRef] = Field(
        default_factory=list,
        description="Parent artifacts for lineage tracking",
    )
    correction_cutoff: CorrectionCutoff | None = Field(
        default=None,
        description="Correction cutoff (REQUIRED for emission)",
    )
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("checksum", mode="before")
    @classmethod
    def validate_checksum(cls, v: str) -> str:
        """Ensure checksum is a valid SHA-256 hex string."""
        if isinstance(v, str) and len(v) == 64:
            return v
        raise ValueError("Checksum must be a valid SHA-256 hex string (64 characters)")

    @field_validator("source_snapshot_id")
    @classmethod
    def validate_source_snapshot_id(cls, v: UUID | None) -> UUID | None:
        """Validate source snapshot is present for emission."""
        return v

    def can_emit(self) -> tuple[bool, str]:
        """Check if artifact can be emitted (has all required fields).

        Returns:
            Tuple of (can_emit, reason)
        """
        if self.source_snapshot_id is None:
            return False, "artifact has no source_snapshot_id"
        if self.correction_cutoff is None:
            return False, "artifact has no correction_cutoff"
        if not self.lineage_refs and self.artifact_type == ArtifactType.RUNTIME_PROFILE:
            return False, "runtime_profile artifact has no lineage_refs"
        return True, ""

    def compute_content_checksum(self) -> str:
        """Compute checksum of artifact content (excluding checksum field itself)."""
        content = self.model_dump(exclude={"id", "checksum", "updated_at"})
        content_str = json.dumps(content, sort_keys=True, default=str)
        return hashlib.sha256(content_str.encode()).hexdigest()


class RuntimeProfilePack(BaseModel):
    """Runtime profile artifact with ZERO raw session text.

    Privacy guarantees:
    - Contains NO raw chat content
    - Only stores content hashes and metadata
    - Disputed hints are excluded
    - Sensitive hints are downgraded by policy
    """

    id: UUID = Field(default_factory=uuid4, description="Unique profile identifier")
    schema_version: SchemaVersion = Field(default_factory=SchemaVersion.current)
    checksum: str = Field(description="SHA-256 checksum of profile content")
    source_snapshot_id: UUID = Field(description="Reference to source session snapshot")
    lineage_refs: list[LineageRef] = Field(
        default_factory=list,
        description="Parent artifacts for lineage tracking",
    )
    correction_cutoff: CorrectionCutoff = Field(
        description="Correction cutoff (REQUIRED)",
    )

    # Profile metadata (NO raw session text)
    session_id: UUID = Field(description="Session identifier")
    profile_type: str = Field(description="Type of runtime profile")
    prompt_hash: str = Field(description="SHA-256 hash of prompt content")
    prompt_length: int = Field(description="Length of original prompt")
    is_redacted: bool = Field(default=False, description="Whether prompt was redacted")
    redacted_reason: str | None = Field(
        default=None,
        description="Reason for redaction if applicable",
    )

    # Hint metadata (NO raw hint content)
    hint_hashes: list[str] = Field(
        default_factory=list,
        description="SHA-256 hashes of included hints",
    )
    disputed_hints_excluded: int = Field(
        default=0,
        description="Count of disputed hints that were excluded",
    )
    sensitive_hints_downgraded: int = Field(
        default=0,
        description="Count of sensitive hints that were downgraded",
    )

    # Agent metadata
    agent_id: str = Field(description="Agent identifier")
    agent_version: str = Field(description="Agent version")

    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def can_emit(self) -> tuple[bool, str]:
        """Check if runtime profile can be emitted."""
        if self.correction_cutoff is None:
            return False, "runtime_profile has no correction_cutoff"
        if self.source_snapshot_id is None:
            return False, "runtime_profile has no source_snapshot_id"
        if not self.lineage_refs:
            return False, "runtime_profile has no lineage_refs"
        return True, ""

    @field_validator("prompt_hash", mode="before")
    @classmethod
    def validate_prompt_hash(cls, v: str) -> str:
        """Ensure prompt_hash is a valid SHA-256 hex string."""
        if isinstance(v, str) and len(v) == 64:
            return v
        raise ValueError("prompt_hash must be a valid SHA-256 hex string")


class AgentEmbodimentPack(BaseModel):
    """Agent embodiment artifact describing agent capabilities."""

    id: UUID = Field(default_factory=uuid4, description="Unique embodiment identifier")
    schema_version: SchemaVersion = Field(default_factory=SchemaVersion.current)
    checksum: str = Field(description="SHA-256 checksum of embodiment content")
    source_snapshot_id: UUID = Field(description="Reference to source snapshot")
    lineage_refs: list[LineageRef] = Field(default_factory=list)
    correction_cutoff: CorrectionCutoff = Field(description="Correction cutoff (REQUIRED)")

    embodiment_type: str = Field(description="Type of embodiment (e.g., 'text', 'voice')")
    capabilities: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    persona_profile: dict[str, Any] = Field(default_factory=dict)

    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def can_emit(self) -> tuple[bool, str]:
        """Check if embodiment pack can be emitted."""
        if self.correction_cutoff is None:
            return False, "agent_embodiment has no correction_cutoff"
        return True, ""


class InteractionPolicyPack(BaseModel):
    """Interaction policy artifact describing interaction rules."""

    id: UUID = Field(default_factory=uuid4, description="Unique policy identifier")
    schema_version: SchemaVersion = Field(default_factory=SchemaVersion.current)
    checksum: str = Field(description="SHA-256 checksum of policy content")
    source_snapshot_id: UUID = Field(description="Reference to source snapshot")
    lineage_refs: list[LineageRef] = Field(default_factory=list)
    correction_cutoff: CorrectionCutoff = Field(description="Correction cutoff (REQUIRED)")

    policy_type: str = Field(description="Type of interaction policy")
    rules: list[dict[str, Any]] = Field(default_factory=list)
    context_requirements: dict[str, Any] = Field(default_factory=dict)

    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def can_emit(self) -> tuple[bool, str]:
        """Check if interaction policy can be emitted."""
        if self.correction_cutoff is None:
            return False, "interaction_policy has no correction_cutoff"
        return True, ""
