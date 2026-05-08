"""Data schemas for relic runtime governance."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class LineageMixin(BaseModel):
    """Mixin for lineage tracking in all entities."""

    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class PromptRecord(LineageMixin):
    """A prompt record with privacy-safe storage."""

    session_id: UUID
    role: str
    content_hash: str
    content_length: int
    is_redacted: bool = False
    original_prompt_id: UUID | None = None


class CorrectionRecord(LineageMixin):
    """A correction record for audit trail."""

    prompt_id: UUID
    correction_type: str
    delta_content: str
    applied: bool = False
    source: str = "manual"


class ArtifactRecord(LineageMixin):
    """An artifact record for the artifact registry."""

    session_id: UUID
    artifact_type: str
    artifact_hash: str
    lineage_path: str = ""
    metadata_json: str = "{}"


class ConsentRecord(LineageMixin):
    """Consent tracking record."""

    session_id: UUID
    consent_type: str
    granted: bool = False
    scope: str = "session"


class SchemaVersion(BaseModel):
    """Schema version record."""

    version: str
    applied_at: datetime = Field(default_factory=datetime.utcnow)
