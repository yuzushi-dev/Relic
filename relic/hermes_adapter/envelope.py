"""
HermesRuntimeEnvelope — Normalized runtime metadata boundary object.

This module defines the envelope that wraps Hermes runtime metadata
for consumption by Relic governance layers. The envelope ensures:
- Consistent field naming and types
- Redaction status tracking
- Session key binding
- Immutable trace correlation
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class MetadataRedactionStatus(str, Enum):
    """
    Redaction status for envelope metadata.

    - redacted: All PII removed, only hashed references present
    - hash_only: Only hashed identifiers stored
    - raw_allowed: Raw identifiers present (requires explicit config)
    """
    REDACTED = "redacted"
    HASH_ONLY = "hash_only"
    RAW_ALLOWED = "raw_allowed"


@dataclass(frozen=True)
class HermesRuntimeEnvelope:
    """
    Normalized Hermes runtime metadata envelope.

    This envelope is created at the Hermes–Relic boundary and passed
    to all Relic governance functions. It ensures consistent access
    to runtime context without exposing raw Hermes internals.
    """

    schema_version: str = "relic.hermes_runtime_envelope.v1"
    trace_id: Optional[str] = None
    session_id: Optional[str] = None
    chat_id: Optional[str] = None
    platform: Optional[str] = None
    channel_ref: Optional[str] = None
    sender_ref: Optional[str] = None
    subject_ref: Optional[str] = None
    hermes_profile_id: Optional[str] = None
    gumi_instance_id: Optional[str] = None
    model: Optional[str] = None
    turn_index: Optional[int] = None
    tool_call_id: Optional[str] = None
    message_ref: Optional[str] = None
    message_hash: Optional[str] = None
    received_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata_redaction_status: MetadataRedactionStatus = MetadataRedactionStatus.HASH_ONLY
    session_key_hash: Optional[str] = None

    def __post_init__(self):
        """Validate envelope constraints."""
        if self.trace_id is not None and len(self.trace_id) < 8:
            raise ValueError("trace_id must be at least 8 characters")
        if self.turn_index is not None and self.turn_index < 0:
            raise ValueError("turn_index must be non-negative")
        if self.message_hash is not None and not self.message_hash.startswith("sha256:"):
            object.__setattr__(self, "message_hash", f"sha256:{self.message_hash}")

    def to_dict(self) -> dict:
        """Convert envelope to dictionary for serialization."""
        return {
            "schema_version": self.schema_version,
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "chat_id": self.chat_id,
            "platform": self.platform,
            "channel_ref": self.channel_ref,
            "sender_ref": self.sender_ref,
            "subject_ref": self.subject_ref,
            "hermes_profile_id": self.hermes_profile_id,
            "gumi_instance_id": self.gumi_instance_id,
            "model": self.model,
            "turn_index": self.turn_index,
            "tool_call_id": self.tool_call_id,
            "message_ref": self.message_ref,
            "message_hash": self.message_hash,
            "received_at": self.received_at.isoformat(),
            "metadata_redaction_status": self.metadata_redaction_status.value,
            "session_key_hash": self.session_key_hash,
        }

    @classmethod
    def from_dict(cls, data: dict) -> HermesRuntimeEnvelope:
        """Create envelope from dictionary."""
        redaction_status = data.get("metadata_redaction_status", "hash_only")
        if isinstance(redaction_status, str):
            redaction_status = MetadataRedactionStatus(redaction_status)

        received_at = data.get("received_at")
        if isinstance(received_at, str):
            received_at = datetime.fromisoformat(received_at.replace("Z", "+00:00"))
        elif received_at is None:
            received_at = datetime.now(timezone.utc)

        return cls(
            schema_version=data.get("schema_version", "relic.hermes_runtime_envelope.v1"),
            trace_id=data.get("trace_id"),
            session_id=data.get("session_id"),
            chat_id=data.get("chat_id"),
            platform=data.get("platform"),
            channel_ref=data.get("channel_ref"),
            sender_ref=data.get("sender_ref"),
            subject_ref=data.get("subject_ref"),
            hermes_profile_id=data.get("hermes_profile_id"),
            gumi_instance_id=data.get("gumi_instance_id"),
            model=data.get("model"),
            turn_index=data.get("turn_index"),
            tool_call_id=data.get("tool_call_id"),
            message_ref=data.get("message_ref"),
            message_hash=data.get("message_hash"),
            received_at=received_at,
            metadata_redaction_status=redaction_status,
            session_key_hash=data.get("session_key_hash"),
        )

    def with_subject_ref(self, subject_ref: str) -> HermesRuntimeEnvelope:
        """Create a new envelope with updated subject_ref."""
        return replace(self, subject_ref=subject_ref)

    def bind_session_key(self, session_key_hash: str) -> HermesRuntimeEnvelope:
        """Create a new envelope with session key bound."""
        return replace(self, session_key_hash=session_key_hash)
