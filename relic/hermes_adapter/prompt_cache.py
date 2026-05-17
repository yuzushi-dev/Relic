"""
Prompt Cache — Cache invalidation policy for Hermes prompts.

This module defines cache policy for Hermes prompt caching,
ensuring that cached prompts are invalidated when subject
profile, policy, or correction state changes.

Design: Hermes caches prompts. Relic governs cache validity.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4


class CacheSection(str, Enum):
    """Cacheable prompt sections."""
    SYSTEM_INSTRUCTIONS = "system_instructions"
    CONTEXT_PACK = "context_pack"
    PROFILE_SUMMARY = "profile_summary"
    MEMORY_HINTS = "memory_hints"
    STYLE_GUIDE = "style_guide"
    SAFETY_RULES = "safety_rules"


class CacheInvalidationReason(str, Enum):
    """Reasons for cache invalidation."""
    PROFILE_CHANGED = "profile_changed"
    POLICY_CHANGED = "policy_changed"
    CORRECTION_APPLIED = "correction_applied"
    CONSENT_CHANGED = "consent_changed"
    EXPLICIT_FLUSH = "explicit_flush"
    TTL_EXPIRED = "ttl_expired"
    SUBJECT_MIGRATION = "subject_migration"


@dataclass(frozen=True)
class CacheKey:
    """
    Cache key for Hermes prompts.

    Attributes:
        key_id: Unique key identifier
        subject_ref: Subject reference
        hermes_profile_id: Hermes profile ID
        sections: Cache sections included
        policy_snapshot_hash: Hash of policy snapshot at cache time
        profile_version: Profile version at cache time
        created_at: Cache creation timestamp
        ttl_seconds: Time-to-live in seconds
    """
    key_id: str
    subject_ref: str
    hermes_profile_id: str
    sections: tuple[CacheSection, ...]
    policy_snapshot_hash: str
    profile_version: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ttl_seconds: int = 3600

    def to_dict(self) -> dict:
        return {
            "key_id": self.key_id,
            "subject_ref": self.subject_ref,
            "hermes_profile_id": self.hermes_profile_id,
            "sections": [s.value for s in self.sections],
            "policy_snapshot_hash": self.policy_snapshot_hash,
            "profile_version": self.profile_version,
            "created_at": self.created_at.isoformat(),
            "ttl_seconds": self.ttl_seconds,
        }

    def is_valid(self, check_time: Optional[datetime] = None) -> bool:
        """Check if cache key is still valid."""
        now = check_time or datetime.now(timezone.utc)
        age = (now - self.created_at).total_seconds()
        return age < self.ttl_seconds

    def includes_section(self, section: CacheSection) -> bool:
        """Check if key includes a specific section."""
        return section in self.sections


@dataclass(frozen=True)
class CacheInvalidation:
    """
    Cache invalidation event.

    Attributes:
        invalidation_id: Unique invalidation identifier
        subject_ref: Subject reference
        reason: Invalidation reason
        affected_sections: Which sections are invalidated
        old_policy_hash: Previous policy snapshot hash
        new_policy_hash: New policy snapshot hash
        created_at: Invalidation timestamp
    """
    invalidation_id: str
    subject_ref: str
    reason: CacheInvalidationReason
    affected_sections: tuple[CacheSection, ...] = ()
    old_policy_hash: Optional[str] = None
    new_policy_hash: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "invalidation_id": self.invalidation_id,
            "subject_ref": self.subject_ref,
            "reason": self.reason.value,
            "affected_sections": [s.value for s in self.affected_sections],
            "old_policy_hash": self.old_policy_hash,
            "new_policy_hash": self.new_policy_hash,
            "created_at": self.created_at.isoformat(),
        }


class PromptCachePolicy:
    """
    Policy manager for Hermes prompt caching.

    This policy ensures that:
    - Cache keys include policy snapshot hash
    - Cache is invalidated on profile/policy/correction changes
    - Subject profile state is never cacheable
    - Consent state invalidates relevant sections

    Args:
        default_ttl_seconds: Default TTL for cache entries (default: 3600)
        max_cache_size: Maximum cache entries per subject (default: 10)
    """

    def __init__(
        self,
        default_ttl_seconds: int = 3600,
        max_cache_size: int = 10,
    ):
        self.default_ttl_seconds = default_ttl_seconds
        self.max_cache_size = max_cache_size
        self._cache: dict[str, CacheKey] = {}
        self._invalidations: list[CacheInvalidation] = []
        self._policy_hashes: dict[str, str] = {}

    def create_cache_key(
        self,
        subject_ref: str,
        hermes_profile_id: str,
        sections: list[CacheSection],
        policy_snapshot_hash: str,
        profile_version: str,
    ) -> CacheKey:
        """
        Create a new cache key.

        Args:
            subject_ref: Subject reference
            hermes_profile_id: Hermes profile ID
            sections: Sections to cache
            policy_snapshot_hash: Current policy snapshot hash
            profile_version: Current profile version

        Returns:
            New CacheKey
        """
        key = CacheKey(
            key_id=f"cache-{uuid4().hex[:12]}",
            subject_ref=subject_ref,
            hermes_profile_id=hermes_profile_id,
            sections=tuple(sections),
            policy_snapshot_hash=policy_snapshot_hash,
            profile_version=profile_version,
            ttl_seconds=self.default_ttl_seconds,
        )

        # Store in cache
        cache_key = f"{subject_ref}:{hermes_profile_id}"
        self._cache[cache_key] = key

        # Enforce max size
        self._enforce_max_size(subject_ref)

        return key

    def invalidate(
        self,
        subject_ref: str,
        reason: CacheInvalidationReason,
        affected_sections: Optional[list[CacheSection]] = None,
        old_policy_hash: Optional[str] = None,
        new_policy_hash: Optional[str] = None,
    ) -> CacheInvalidation:
        """
        Invalidate cache for subject.

        Args:
            subject_ref: Subject reference
            reason: Invalidation reason
            affected_sections: Which sections are affected
            old_policy_hash: Previous policy hash
            new_policy_hash: New policy hash

        Returns:
            CacheInvalidation record
        """
        invalidation = CacheInvalidation(
            invalidation_id=f"invalidation-{uuid4().hex[:12]}",
            subject_ref=subject_ref,
            reason=reason,
            affected_sections=tuple(affected_sections or []),
            old_policy_hash=old_policy_hash,
            new_policy_hash=new_policy_hash,
        )

        self._invalidations.append(invalidation)

        # Remove cached keys for this subject
        keys_to_remove = [
            k for k in self._cache.keys()
            if k.startswith(f"{subject_ref}:")
        ]
        for key in keys_to_remove:
            del self._cache[key]

        # Update policy hash if provided
        if new_policy_hash:
            self._policy_hashes[subject_ref] = new_policy_hash

        return invalidation

    def is_cacheable(self, section: CacheSection) -> bool:
        """
        Check if a section is allowed to be cached.

        Profile sections are never cacheable.

        Args:
            section: Section to check

        Returns:
            True if cacheable
        """
        # Subject profile state is never cacheable
        non_cacheable = {
            CacheSection.PROFILE_SUMMARY,
        }
        return section not in non_cacheable

    def is_valid(
        self,
        key: CacheKey,
        current_policy_hash: str,
        current_profile_version: str,
    ) -> bool:
        """
        Check if cache key is valid against current state.

        Args:
            key: Cache key to validate
            current_policy_hash: Current policy snapshot hash
            current_profile_version: Current profile version

        Returns:
            True if cache is valid
        """
        # Check TTL
        if not key.is_valid():
            return False

        # Check policy hash
        if key.policy_snapshot_hash != current_policy_hash:
            return False

        # Check profile version
        if key.profile_version != current_profile_version:
            return False

        return True

    def _enforce_max_size(self, subject_ref: str) -> None:
        """Enforce maximum cache size per subject."""
        subject_keys = [k for k in self._cache.keys() if k.startswith(f"{subject_ref}:")]
        if len(subject_keys) > self.max_cache_size:
            # Remove oldest
            oldest_key = min(
                subject_keys,
                key=lambda k: self._cache[k].created_at,
            )
            del self._cache[oldest_key]

    def get_invalidation_history(
        self,
        subject_ref: str,
        limit: int = 10,
    ) -> list[CacheInvalidation]:
        """Get recent invalidation history for subject."""
        subject_invalidations = [
            i for i in self._invalidations
            if i.subject_ref == subject_ref
        ]
        return subject_invalidations[-limit:]


# Convenience functions

_default_policy: Optional[PromptCachePolicy] = None
_policy_lock = threading.Lock()


def get_cache_policy() -> PromptCachePolicy:
    """Get or create default PromptCachePolicy."""
    global _default_policy
    if _default_policy is None:
        with _policy_lock:
            if _default_policy is None:
                _default_policy = PromptCachePolicy()
    return _default_policy
