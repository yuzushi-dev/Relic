"""
Identity Mapper, Maps Hermes identifiers to Relic subject references.

This module handles the critical boundary between Hermes runtime IDs
and Relic subject references. It ensures:
- Platform-scoped IDs are hashed before storage
- User, subject, Gumi instance, Hermes profile, and platform thread remain distinct
- Multi-chat → single-subject mapping requires explicit consent
- No raw user data is exposed in traces
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from relic.hermes_adapter.state_store import StateStore


class MappingStrategy(str, Enum):
    """
    Strategy for mapping sender_id to subject_ref.

    - DIRECT: Use sender_id as subject_ref (development only)
    - HASHED: Hash sender_id with platform scope
    - CONFIGURED: Use explicit mapping from configuration
    - CONSENT_BASED: Require explicit consent for multi-chat mapping
    """
    DIRECT = "direct"
    HASHED = "hashed"
    CONFIGURED = "configured"
    CONSENT_BASED = "consent_based"


@dataclass(frozen=True)
class SubjectMapping:
    """
    Result of identity mapping operation.

    Attributes:
        subject_ref: The resolved subject reference for Relic
        sender_ref: Hashed sender reference
        platform_scope: Platform identifier for scoping
        mapping_strategy: Strategy used for mapping
        consent_required: Whether consent is required for this mapping
        consent_granted: Whether consent was granted (if required)
        mapped_at: UTC timestamp of mapping
    """

    subject_ref: str
    sender_ref: str
    platform_scope: str
    mapping_strategy: MappingStrategy
    consent_required: bool = False
    consent_granted: bool = True
    mapped_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        """Convert mapping to dictionary."""
        return {
            "subject_ref": self.subject_ref,
            "sender_ref": self.sender_ref,
            "platform_scope": self.platform_scope,
            "mapping_strategy": self.mapping_strategy.value,
            "consent_required": self.consent_required,
            "consent_granted": self.consent_granted,
            "mapped_at": self.mapped_at.isoformat(),
        }


class IdentityMapper:
    """
    Maps Hermes identifiers to Relic subject references.

    This mapper enforces the boundary rule: never assume sender_id == subject_id.
    All platform-scoped IDs are hashed before storage or trace export.
    """

    def __init__(
        self,
        mapping_strategy: MappingStrategy = MappingStrategy.HASHED,
        explicit_mappings: Optional[dict[str, str]] = None,
        consent_store: Optional[dict[str, bool]] = None,
        persist: bool = False,
    ):
        self.mapping_strategy = mapping_strategy
        self.explicit_mappings = explicit_mappings or {}
        self._persist_store: Optional[StateStore] = None
        if persist and consent_store is None:
            self._persist_store = StateStore("consent_store")
            # Bootstrap in-memory dict from persisted state.
            self.consent_store: dict[str, bool] = {
                k: bool(v) for k, v in self._persist_store.all().items()
            }
        else:
            self.consent_store = dict(consent_store) if consent_store else {}

    def map_sender_to_subject(
        self,
        sender_id: str,
        platform: str,
        gumi_instance_id: str,
        hermes_profile_id: str,
        chat_id: Optional[str] = None,
    ) -> SubjectMapping:
        """
        Map a Hermes sender_id to a Relic subject_ref.

        Args:
            sender_id: Hermes sender identifier
            platform: Platform identifier (e.g., "telegram", "whatsapp")
            gumi_instance_id: Gumi instance identifier
            hermes_profile_id: Hermes profile identifier
            chat_id: Optional chat/thread ID for multi-chat scenarios

        Returns:
            SubjectMapping with resolved subject_ref and metadata

        Raises:
            ValueError: If required parameters are missing
            ConsentRequiredError: If consent is required but not granted
        """
        if not sender_id:
            raise ValueError("sender_id is required")
        if not platform:
            raise ValueError("platform is required")
        if not gumi_instance_id:
            raise ValueError("gumi_instance_id is required")
        if not hermes_profile_id:
            raise ValueError("hermes_profile_id is required")

        # Check for explicit mapping first
        if self.mapping_strategy == MappingStrategy.CONFIGURED:
            mapping_key = f"{platform}:{sender_id}:{hermes_profile_id}"
            if mapping_key in self.explicit_mappings:
                subject_ref = self.explicit_mappings[mapping_key]
                return self._create_mapping(
                    subject_ref=subject_ref,
                    sender_id=sender_id,
                    platform=platform,
                    strategy=MappingStrategy.CONFIGURED,
                    consent_granted=True,
                )

        # Handle multi-chat scenarios with consent-based mapping
        if chat_id and self.mapping_strategy == MappingStrategy.CONSENT_BASED:
            consent_key = f"{sender_id}:{platform}"
            consent_granted = self.consent_store.get(consent_key, False)
            if not consent_granted:
                raise ConsentRequiredError(
                    f"Consent required for multi-chat mapping: {consent_key}"
                )
            subject_ref = self._hash_subject_id(sender_id, platform, gumi_instance_id, hermes_profile_id)
            return self._create_mapping(
                subject_ref=subject_ref,
                sender_id=sender_id,
                platform=platform,
                strategy=MappingStrategy.CONSENT_BASED,
                consent_granted=True,
            )

        # Default: use hashed mapping
        subject_ref = self._hash_subject_id(sender_id, platform, gumi_instance_id, hermes_profile_id)
        return self._create_mapping(
            subject_ref=subject_ref,
            sender_id=sender_id,
            platform=platform,
            strategy=self.mapping_strategy,
            consent_granted=True,
        )

    def _hash_subject_id(
        self,
        sender_id: str,
        platform: str,
        gumi_instance_id: str,
        hermes_profile_id: str,
    ) -> str:
        """Create a hashed subject reference scoped to platform/Gumi/Hermes profile."""
        composite = f"{sender_id}:{platform}:{gumi_instance_id}:{hermes_profile_id}"
        return hashlib.sha256(composite.encode()).hexdigest()

    def _hash_sender_id(self, sender_id: str, platform: str) -> str:
        """Create a hashed sender reference scoped to platform."""
        composite = f"{sender_id}:{platform}"
        return hashlib.sha256(composite.encode()).hexdigest()

    def _create_mapping(
        self,
        subject_ref: str,
        sender_id: str,
        platform: str,
        strategy: MappingStrategy,
        consent_granted: bool = True,
    ) -> SubjectMapping:
        """Create a SubjectMapping result."""
        sender_ref = self._hash_sender_id(sender_id, platform)
        consent_required = strategy == MappingStrategy.CONSENT_BASED

        return SubjectMapping(
            subject_ref=subject_ref,
            sender_ref=sender_ref,
            platform_scope=platform,
            mapping_strategy=strategy,
            consent_required=consent_required,
            consent_granted=consent_granted,
        )

    def register_explicit_mapping(
        self,
        sender_id: str,
        platform: str,
        hermes_profile_id: str,
        subject_ref: str,
    ) -> None:
        """Register an explicit sender_id → subject_id mapping."""
        mapping_key = f"{platform}:{sender_id}:{hermes_profile_id}"
        self.explicit_mappings[mapping_key] = subject_ref

    def grant_consent(self, sender_id: str, platform: str) -> None:
        """Grant consent for multi-chat mapping (persisted if persist=True)."""
        consent_key = f"{sender_id}:{platform}"
        self.consent_store[consent_key] = True
        if self._persist_store is not None:
            self._persist_store.set(consent_key, True)

    def revoke_consent(self, sender_id: str, platform: str) -> None:
        """Revoke consent for multi-chat mapping (persisted if persist=True)."""
        consent_key = f"{sender_id}:{platform}"
        self.consent_store.pop(consent_key, None)
        if self._persist_store is not None:
            self._persist_store.delete(consent_key)


class ConsentRequiredError(Exception):
    """Raised when consent is required but not granted for mapping."""

    def __init__(self, message: str, consent_key: Optional[str] = None):
        super().__init__(message)
        self.consent_key = consent_key
