"""Chronicle schema — Pydantic models for events, decisions, snapshots, provenance edges.

Module: relic.chronicle.schema
Version: chronicle-schema/v1
Reference: docs/chronicle/agentic-development-plan.md §6.6, T010

Enum source-of-truth (NEVER duplicate locally):
  - PrivacyLevel      → relic.persistence.PrivacyLevel
  - ConsentType       → relic.control.consent.ConsentType
  - IncidentSeverity  → relic.control.incident.IncidentSeverity
  - ArtifactType      → relic.artifacts.types.ArtifactType
  - CorrectionType    → relic.correction.propagation.CorrectionType

This module defines Chronicle-specific models only.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Reuse existing enums from Relic core — do NOT duplicate
from relic.persistence import PrivacyLevel

try:
    from relic.control.consent import ConsentType
except Exception:
    ConsentType = None  # type: ignore[assignment, misc]

# Chronicle enums
from relic.chronicle.enums import (
    AccessKind,
    EventCategory,
    ProximityOrder,
    ReasoningCapture,
    RetentionPolicy,
    Severity,
    ValidationStatus,
    VisibilityLevel,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_EVENT_TYPE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_PAYLOAD_HASH_RE = re.compile(r"^sha256:[0-9a-f]{16,64}$")
_TAG_RE = re.compile(r"^[a-z_]+:[\w-]+$")

# Allowed consent_basis values: ConsentType enum values + legitimate-interest bases.
# ConsentType values are lowercase (memory_storage, analytics, roleplay, data_sharing);
# legitimate interest bases are uppercase per plan §9.3 (SAFETY, PRIVACY, INCIDENT).
_LEGITIMATE_INTEREST_BASES = {"SAFETY", "PRIVACY", "INCIDENT"}


def _allowed_consent_bases() -> set[str]:
    """Compute the set of accepted consent_basis values lazily.

    Lazy import avoids circular dependency and keeps Chronicle decoupled
    from relic.control.consent at module load time.
    """
    bases = set(_LEGITIMATE_INTEREST_BASES)
    if ConsentType is not None:
        try:
            bases.update(ct.value for ct in ConsentType)
        except Exception:  # pragma: no cover
            pass
    return bases


def _validate_consent_basis(v: str | None) -> str | None:
    if v is None:
        return v
    if v in _allowed_consent_bases():
        return v
    raise ValueError(
        f"consent_basis '{v}' not in allowed set "
        f"(ConsentType values or {sorted(_LEGITIMATE_INTEREST_BASES)})"
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sort_json_dumps(data: dict) -> str:
    """Serialize dict to JSON with sorted keys (Pydantic v2 compatible)."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


# ---------------------------------------------------------------------------
# Event model
# ---------------------------------------------------------------------------

class Event(BaseModel):
    """Chronicle event — atomic, immutable fact that happened.

    Corresponds to the `chronicle_events` table (migration 0003).
    """

    model_config = ConfigDict(
        populate_by_name=True,
        str_strip_whitespace=True,
    )

    event_id: UUID = Field(default_factory=uuid.uuid4)
    event_type: str = Field(..., description="snake_case event type, e.g. model_called, memory_write")
    event_category: EventCategory

    # Trace correlation IDs
    trace_id: UUID
    run_id: UUID | None = None
    session_id: UUID | None = None
    parent_event_id: UUID | None = None
    experiment_id: UUID | None = None

    # Subject / actor identification
    subject_id: str | None = None
    agent_id: str | None = None
    profile_id: str | None = None
    hermes_profile_id: str | None = None
    actor_type: str | None = None
    actor_id: str | None = None

    # Module paths
    source_module: str
    target_module: str | None = None

    # Timing
    timestamp: str = Field(default_factory=_utc_now)
    duration_ms: float | None = None

    # References
    input_refs: list[str] = Field(default_factory=list)
    output_refs: list[str] = Field(default_factory=list)

    # Payload (redacted, hashed — never raw content)
    payload_redacted: bool = False
    payload_hash: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)

    # Governance
    sensitivity: PrivacyLevel = PrivacyLevel.SAFE
    visibility: VisibilityLevel = VisibilityLevel.RESEARCHER
    consent_basis: str | None = None
    retention_policy: RetentionPolicy = RetentionPolicy.STANDARD_365D

    # Tags and severity
    tags: list[str] = Field(default_factory=list)
    severity: str = "info"

    # Metadata
    validation_status: str | None = None
    error_code: str | None = None
    retry_count: int = 0
    schema_version: str = "chronicle-event/v1"
    created_at: str = Field(default_factory=_utc_now)

    @field_validator("event_type")
    @classmethod
    def _validate_event_type(cls, v: str) -> str:
        if not _EVENT_TYPE_RE.match(v):
            raise ValueError(
                f"event_type must be snake_case lowercase, got '{v}'"
            )
        return v

    @field_validator("payload_hash")
    @classmethod
    def _validate_payload_hash(cls, v: str | None) -> str | None:
        if v is not None and not _PAYLOAD_HASH_RE.match(v):
            raise ValueError(
                f"payload_hash must match sha256:<16-64 hex>, got '{v}'"
            )
        return v

    @field_validator("tags", mode="after")
    @classmethod
    def _validate_tags(cls, v: list[str]) -> list[str]:
        for tag in v:
            if not _TAG_RE.match(tag):
                raise ValueError(
                    f"tag '{tag}' must match format 'key:value' (lowercase, underscore allowed)"
                )
        return v

    @field_validator("consent_basis")
    @classmethod
    def _check_consent_basis(cls, v: str | None) -> str | None:
        return _validate_consent_basis(v)

    def to_json(self) -> str:
        """Serialize to sorted JSON string."""
        return _sort_json_dumps(self.model_dump(mode="json"))

    def to_db_row(self) -> dict[str, Any]:
        """Convert to SQLite row dict (JSON columns serialized as text)."""
        row = self.model_dump()
        row["event_id"] = str(row["event_id"])
        row["trace_id"] = str(row["trace_id"])
        # Convert enum values to strings for DB
        row["sensitivity"] = row["sensitivity"].value if hasattr(row["sensitivity"], "value") else str(row["sensitivity"])
        row["visibility"] = row["visibility"].value if hasattr(row["visibility"], "value") else str(row["visibility"])
        row["retention_policy"] = row["retention_policy"].value if hasattr(row["retention_policy"], "value") else str(row["retention_policy"])
        row["event_category"] = row["event_category"].value if hasattr(row["event_category"], "value") else str(row["event_category"])
        for opt_field in ("run_id", "session_id", "parent_event_id", "experiment_id"):
            if row.get(opt_field) is not None:
                row[opt_field] = str(row[opt_field])
        # Serialize lists/dicts as JSON strings
        for field_name in ("input_refs", "output_refs", "payload", "tags"):
            val = row.get(field_name)
            if isinstance(val, (list, dict)):
                row[field_name] = json.dumps(val, sort_keys=True)
        return row


# ---------------------------------------------------------------------------
# Decision model
# ---------------------------------------------------------------------------

class Decision(BaseModel):
    """Chronicle decision — a choice made by agent/rule/user/system.

    Corresponds to the `chronicle_decisions` table (migration 0004).
    """

    model_config = ConfigDict(
        populate_by_name=True,
        str_strip_whitespace=True,
    )

    decision_id: UUID = Field(default_factory=uuid.uuid4)
    trace_id: UUID
    run_id: UUID | None = None
    session_id: UUID | None = None
    subject_id: str | None = None

    actor_type: str | None = None
    actor_id: str | None = None
    decision_kind: str

    # Action taken and alternatives considered
    selected_action: dict[str, Any] = Field(default_factory=dict)
    rejected_alternatives: list[dict[str, Any]] = Field(default_factory=list)

    # Observable inputs and outputs
    observable_inputs: dict[str, Any] = Field(default_factory=dict)
    observable_outputs: dict[str, Any] = Field(default_factory=dict)

    # Confidence and uncertainty
    confidence: float | None = None
    uncertainty_notes: str | None = None

    # Evidence and rationale
    evidence_refs: list[str] = Field(default_factory=list)
    rationale_summary: str | None = None  # ≤ 280 char enforced

    # Governance
    consent_basis: str | None = None
    sensitivity: PrivacyLevel = PrivacyLevel.SAFE
    validation_status: ValidationStatus = ValidationStatus.PENDING

    # Timing
    timestamp: str = Field(default_factory=_utc_now)
    schema_version: str = "chronicle-decision/v1"
    created_at: str = Field(default_factory=_utc_now)

    @field_validator("rationale_summary")
    @classmethod
    def _validate_rationale_summary(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 280:
            raise ValueError(f"rationale_summary must be ≤ 280 chars, got {len(v)}")
        return v

    @field_validator("consent_basis")
    @classmethod
    def _check_consent_basis(cls, v: str | None) -> str | None:
        return _validate_consent_basis(v)

    def to_json(self) -> str:
        return _sort_json_dumps(self.model_dump(mode="json"))

    def to_db_row(self) -> dict[str, Any]:
        row = self.model_dump()
        row["decision_id"] = str(row["decision_id"])
        row["trace_id"] = str(row["trace_id"])
        row["sensitivity"] = row["sensitivity"].value if hasattr(row["sensitivity"], "value") else str(row["sensitivity"])
        row["validation_status"] = row["validation_status"].value if hasattr(row["validation_status"], "value") else str(row["validation_status"])
        for opt_field in ("run_id", "session_id"):
            if row.get(opt_field) is not None:
                row[opt_field] = str(row[opt_field])
        for field_name in ("selected_action", "rejected_alternatives", "observable_inputs", "observable_outputs"):
            val = row.get(field_name)
            if isinstance(val, (list, dict)):
                row[field_name] = json.dumps(val, sort_keys=True)
        if isinstance(row.get("evidence_refs"), list):
            row["evidence_refs"] = json.dumps(row["evidence_refs"], sort_keys=True)
        return row


# ---------------------------------------------------------------------------
# StateSnapshot model
# ---------------------------------------------------------------------------

class StateSnapshot(BaseModel):
    """Chronicle state snapshot — point-in-time photograph of system state.

    Corresponds to the `chronicle_state_snapshots` table (migration 0005).
    """

    model_config = ConfigDict(
        populate_by_name=True,
        str_strip_whitespace=True,
    )

    snapshot_id: UUID = Field(default_factory=uuid.uuid4)
    snapshot_type: str
    subject_id: str | None = None
    scope_ref: str | None = None
    trace_id: UUID | None = None

    captured_at: str = Field(default_factory=_utc_now)
    trigger_event_id: UUID | None = None
    previous_snapshot_id: UUID | None = None

    content_hash: str
    content_ref: str | None = None
    content_size_bytes: int | None = None

    diff_from_previous: dict[str, Any] | None = None

    sensitivity: PrivacyLevel = PrivacyLevel.SAFE
    retention_policy: RetentionPolicy = RetentionPolicy.STANDARD_365D

    schema_version: str = "chronicle-snapshot/v1"
    created_at: str = Field(default_factory=_utc_now)

    @field_validator("content_hash")
    @classmethod
    def _validate_content_hash(cls, v: str) -> str:
        if not _PAYLOAD_HASH_RE.match(v):
            raise ValueError(f"content_hash must match sha256:<hex>, got '{v}'")
        return v

    def to_json(self) -> str:
        return _sort_json_dumps(self.model_dump(mode="json"))

    def to_db_row(self) -> dict[str, Any]:
        row = self.model_dump()
        row["snapshot_id"] = str(row["snapshot_id"])
        row["sensitivity"] = row["sensitivity"].value if hasattr(row["sensitivity"], "value") else str(row["sensitivity"])
        row["retention_policy"] = row["retention_policy"].value if hasattr(row["retention_policy"], "value") else str(row["retention_policy"])
        for opt_field in ("trigger_event_id", "previous_snapshot_id", "trace_id"):
            if row.get(opt_field) is not None:
                row[opt_field] = str(row[opt_field])
        if isinstance(row.get("diff_from_previous"), dict):
            row["diff_from_previous"] = json.dumps(row["diff_from_previous"], sort_keys=True)
        return row


# ---------------------------------------------------------------------------
# ProvenanceEdge model
# ---------------------------------------------------------------------------

class ProvenanceEdge(BaseModel):
    """Chronicle provenance edge — directed arc in the artifact provenance graph."""

    model_config = ConfigDict(
        populate_by_name=True,
        str_strip_whitespace=True,
    )

    edge_id: UUID = Field(default_factory=uuid.uuid4)
    trace_id: UUID
    artifact_id: UUID

    from_node_type: str
    from_node_id: UUID

    relation: ProximityOrder

    contribution_role: str | None = None
    weight: float = 1.0

    timestamp: str = Field(default_factory=_utc_now)
    schema_version: str = "chronicle-provenance/v1"
    created_at: str = Field(default_factory=_utc_now)

    def to_json(self) -> str:
        return _sort_json_dumps(self.model_dump(mode="json"))

    def to_db_row(self) -> dict[str, Any]:
        row = self.model_dump()
        row["edge_id"] = str(row["edge_id"])
        row["trace_id"] = str(row["trace_id"])
        row["artifact_id"] = str(row["artifact_id"])
        row["from_node_id"] = str(row["from_node_id"])
        row["relation"] = row["relation"].value if hasattr(row["relation"], "value") else str(row["relation"])
        return row


# ---------------------------------------------------------------------------
# AccessLogEntry model
# ---------------------------------------------------------------------------

class AccessLogEntry(BaseModel):
    """Chronicle access log entry — audit trail of every Chronicle data access."""

    model_config = ConfigDict(
        populate_by_name=True,
        str_strip_whitespace=True,
    )

    access_id: UUID = Field(default_factory=uuid.uuid4)
    trace_id: UUID | None = None
    accessor_id: str
    access_kind: AccessKind

    target_filter: dict[str, Any] = Field(default_factory=dict)
    rows_returned: int = 0
    result_hash: str | None = None

    reason: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None

    timestamp: str = Field(default_factory=_utc_now)
    schema_version: str = "chronicle-access/v1"
    created_at: str = Field(default_factory=_utc_now)

    def to_json(self) -> str:
        return _sort_json_dumps(self.model_dump(mode="json"))

    def to_db_row(self) -> dict[str, Any]:
        row = self.model_dump()
        row["access_id"] = str(row["access_id"])
        if row.get("trace_id") is not None:
            row["trace_id"] = str(row["trace_id"])
        row["access_kind"] = row["access_kind"].value if hasattr(row["access_kind"], "value") else str(row["access_kind"])
        if isinstance(row.get("target_filter"), dict):
            row["target_filter"] = json.dumps(row["target_filter"], sort_keys=True)
        return row
