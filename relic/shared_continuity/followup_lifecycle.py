"""
PR33G, Follow-Up Lifecycle and Cron Decision

Follow-up lifecycle with due selection, TTL, ignored-expire, pause, and max attempts.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from enum import Enum


class FollowupStatus(str, Enum):
    PENDING = "pending"
    DUE = "due"
    SENT = "sent"
    ACKNOWLEDGED = "acknowledged"
    IGNORED = "ignored"
    EXHAUSTED = "exhausted"
    EXPIRED = "expired"


@dataclass
class FollowupCandidate:
    followup_id: str
    marker_id: str
    subject_id: str
    gumi_instance_id: str
    hermes_profile_id: str

    max_attempts: int
    attempt_count: int
    status: FollowupStatus

    followup_interval_seconds: int
    next_followup_at: Optional[str]
    ttl_seconds: int
    created_at: str
    expires_at: Optional[str]

    is_paused: bool
    paused_at: Optional[str]


class FollowupLifecycle:
    """Follow-up lifecycle management for Shared Continuity Memory."""

    def __init__(self):
        self._followups: Dict[str, FollowupCandidate] = {}
        self._paused_scopes: Dict[str, Dict[str, Any]] = {}

    def is_scope_paused(
        self,
        subject_id: str,
        scope_name: str = "global",
        gumi_instance_id: Optional[str] = None,
        hermes_profile_id: Optional[str] = None,
    ) -> bool:
        """Check if a scope is paused."""
        scope_key = f"{subject_id}:{gumi_instance_id}:{hermes_profile_id}:{scope_name}"
        return self._paused_scopes.get(scope_key, {}).get("is_paused", False)

    def create_followup(
        self,
        followup_id: str,
        marker_id: str,
        subject_id: str,
        gumi_instance_id: str,
        hermes_profile_id: str,
        max_attempts: int = 3,
        followup_interval_seconds: int = 86400,
        ttl_seconds: int = 604800,
    ) -> FollowupCandidate:
        """Create a new followup."""
        now = datetime.now().isoformat() + "Z"
        next_followup = (datetime.now() + timedelta(seconds=followup_interval_seconds)).isoformat() + "Z"
        expires_at = (datetime.now() + timedelta(seconds=ttl_seconds)).isoformat() + "Z"

        followup = FollowupCandidate(
            followup_id=followup_id,
            marker_id=marker_id,
            subject_id=subject_id,
            gumi_instance_id=gumi_instance_id,
            hermes_profile_id=hermes_profile_id,
            max_attempts=max_attempts,
            attempt_count=0,
            status=FollowupStatus.PENDING,
            followup_interval_seconds=followup_interval_seconds,
            next_followup_at=next_followup,
            ttl_seconds=ttl_seconds,
            created_at=now,
            expires_at=expires_at,
            is_paused=False,
            paused_at=None,
        )

        self._followups[followup_id] = followup
        return followup

    def select_due_followups(
        self,
        subject_id: str,
        gumi_instance_id: Optional[str] = None,
        hermes_profile_id: Optional[str] = None,
        scope_name: str = "global",
    ) -> List[Dict[str, Any]]:
        """
        Select follow-ups that are due for sending.
        BLOCKED_FOLLOWUP_AFTER_MAX_ATTEMPTS: Don't select if exhausted
        BLOCKED_FOLLOWUP_IGNORES_TTL: Don't select if expired
        BLOCKED_FOLLOWUP_IGNORES_PAUSE: Don't select if scope is paused
        """
        results = []

        for followup_id, followup in self._followups.items():
            # Scope check
            if followup.subject_id != subject_id:
                continue

            if gumi_instance_id and followup.gumi_instance_id != gumi_instance_id:
                continue

            if hermes_profile_id and followup.hermes_profile_id != hermes_profile_id:
                continue

            # BLOCKED_FOLLOWUP_IGNORES_PAUSE: Check if scope is paused
            if self.is_scope_paused(subject_id, scope_name, gumi_instance_id, hermes_profile_id):
                continue

            # BLOCKED_FOLLOWUP_AFTER_MAX_ATTEMPTS: Check max attempts
            if followup.attempt_count >= followup.max_attempts:
                followup.status = FollowupStatus.EXHAUSTED
                continue

            # BLOCKED_FOLLOWUP_IGNORES_TTL: Check TTL expiration
            if followup.expires_at:
                try:
                    expires_dt = datetime.fromisoformat(followup.expires_at.replace("Z", "+00:00"))
                    if datetime.now() > expires_dt:
                        followup.status = FollowupStatus.EXPIRED
                        continue
                except (ValueError, TypeError):
                    pass

            # Check status for due
            if followup.status in [FollowupStatus.PENDING, FollowupStatus.DUE]:
                # Check if next_followup_at has passed
                if followup.next_followup_at:
                    try:
                        next_dt = datetime.fromisoformat(followup.next_followup_at.replace("Z", "+00:00"))
                        if datetime.now() >= next_dt:
                            results.append({
                                "followup_id": followup_id,
                                "marker_id": followup.marker_id,
                                "subject_id": followup.subject_id,
                                "status": followup.status.value if isinstance(followup.status, Enum) else followup.status,
                                "attempt_count": followup.attempt_count,
                                "max_attempts": followup.max_attempts,
                            })
                    except (ValueError, TypeError):
                        pass

        return results

    def mark_sent(
        self,
        followup_id: str,
    ) -> None:
        """Mark a followup as sent and increment attempt count."""
        if followup_id not in self._followups:
            return

        followup = self._followups[followup_id]
        followup.attempt_count += 1
        followup.status = FollowupStatus.SENT

        # Schedule next followup
        followup.next_followup_at = (
            datetime.now() + timedelta(seconds=followup.followup_interval_seconds)
        ).isoformat() + "Z"

        # Check if exhausted
        if followup.attempt_count >= followup.max_attempts:
            followup.status = FollowupStatus.EXHAUSTED

    def mark_acknowledged(self, followup_id: str) -> None:
        """Mark a followup as acknowledged."""
        if followup_id not in self._followups:
            return

        self._followups[followup_id].status = FollowupStatus.ACKNOWLEDGED

    def mark_ignored(self, followup_id: str) -> None:
        """Mark a followup as ignored."""
        if followup_id not in self._followups:
            return

        followup = self._followups[followup_id]
        followup.status = FollowupStatus.IGNORED

        # Set TTL for expiration
        followup.expires_at = (datetime.now() + timedelta(seconds=followup.ttl_seconds)).isoformat() + "Z"

    def pause_scope(
        self,
        subject_id: str,
        scope_name: str = "global",
        gumi_instance_id: Optional[str] = None,
        hermes_profile_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Pause follow-ups for a scope."""
        scope_key = f"{subject_id}:{gumi_instance_id}:{hermes_profile_id}:{scope_name}"

        self._paused_scopes[scope_key] = {
            "is_paused": True,
            "paused_at": datetime.now().isoformat() + "Z",
            "subject_id": subject_id,
            "gumi_instance_id": gumi_instance_id,
            "hermes_profile_id": hermes_profile_id,
            "scope_name": scope_name,
        }

        return self._paused_scopes[scope_key]

    def resume_scope(
        self,
        subject_id: str,
        scope_name: str = "global",
        gumi_instance_id: Optional[str] = None,
        hermes_profile_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Resume follow-ups for a scope."""
        scope_key = f"{subject_id}:{gumi_instance_id}:{hermes_profile_id}:{scope_name}"

        if scope_key in self._paused_scopes:
            self._paused_scopes[scope_key]["is_paused"] = False
            self._paused_scopes[scope_key]["resumed_at"] = datetime.now().isoformat() + "Z"

        return {"subject_id": subject_id, "scope_name": scope_name, "is_paused": False}


def get_followup_lifecycle() -> FollowupLifecycle:
    """Get the global followup lifecycle instance."""
    return FollowupLifecycle()