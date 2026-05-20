"""
PR33D — Relic Continuity Service

Service implementing remember, correct, due_followups, recent_markers,
forget, pause, and resume operations for Shared Continuity Memory.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from enum import Enum


class MarkerStatus(str, Enum):
    ACTIVE = "active"
    RETIRED = "retired"
    REJECTED = "rejected"
    EXPIRED = "expired"
    FORGOTTEN = "forgotten"
    CORRECTED = "corrected"


class FollowupStatus(str, Enum):
    PENDING = "pending"
    DUE = "due"
    SENT = "sent"
    ACKNOWLEDGED = "acknowledged"
    IGNORED = "ignored"
    EXHAUSTED = "exhausted"
    EXPIRED = "expired"


RUNTIME_RECALL_SOURCE_TYPES = {
    "user_confirmed",
    "subject_confirmed",
    "subject_requested",
    "subject_corrected",
    "hindsight",
    "diary_entry",
}

FORBIDDEN_RUNTIME_SOURCE_TYPES = {
    "hindsight_safety_signal",
    "researcher_only_note",
    "sensitive_signal",
}


@dataclass
class ContinuityMarker:
    marker_id: str
    subject_id: str
    gumi_instance_id: str
    hermes_profile_id: str

    subject_confirmation: bool
    source_type: str
    created_at: str

    subject_words: List[str]
    gumi_agreed_words: List[str]
    raw_source_text: Optional[str]

    status: MarkerStatus
    gumi_recall_allowed: bool

    recall_count: int
    max_recall_count: int
    ttl_seconds: int

    expires_at: Optional[str]
    updated_at: Optional[str]

    candidate_for_confirmation: bool = False
    clinical_interpretation_allowed: bool = False

    # Replacement chain fields
    previous_version_id: Optional[str] = None
    final_subject_words: Optional[List[str]] = None
    next_version_id: Optional[str] = None

    # Validated curated labels (clinical-checked at write time; persisted for read-path)
    normalized_tags: Optional[List[str]] = None
    gumi_words: Optional[List[str]] = None


@dataclass
class ContinuityFollowup:
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
    resumed_at: Optional[str]


@dataclass
class ContinuityCorrection:
    correction_id: str
    marker_id: str
    subject_id: str
    gumi_instance_id: str
    hermes_profile_id: str

    authoritative: bool
    subject_words: List[str]
    gumi_agreed_words: List[str]
    correction_note: Optional[str]

    status: str
    created_at: str
    created_by: str

    original_marker_id: str
    is_replacement: bool


class ContinuityServiceError(Exception):
    """Continuity service error with code and message."""
    BLOCKED_CLINICALIZATION_IN_MARKER = "BLOCKED_CLINICALIZATION_IN_MARKER: Forbidden clinical terms in normalized tags or gumi words"
    BLOCKED_MARKER_WITHOUT_SUBJECT_SCOPE = "BLOCKED_MARKER_WITHOUT_SUBJECT_SCOPE: All scope fields required"
    BLOCKED_MARKER_WITHOUT_SUBJECT_CONFIRMATION = "BLOCKED_MARKER_WITHOUT_SUBJECT_CONFIRMATION: Subject confirmation required"
    BLOCKED_CORRECTION_NOT_AUTHORITATIVE = "BLOCKED_CORRECTION_NOT_AUTHORITATIVE: Scope mismatch"
    MARKER_NOT_FOUND = "MARKER_NOT_FOUND"

    def __init__(self, code: str, message: str = ""):
        self.code = code
        self.message = message or code
        super().__init__(self.message)

    def __str__(self) -> str:
        return self.message

    def __eq__(self, other) -> bool:
        if isinstance(other, ContinuityServiceError):
            return self.code == other.code
        return self.code == other

    def __hash__(self) -> int:
        return hash(self.code)


# Forbidden clinical terms - never appear in service output
FORBIDDEN_CLINICAL_TERMS = {
    "bipolar", "mania", "hypomania", "depression", "depressed",
    "episode", "symptom", "symptom-related", "diagnosis", "diagnostic",
    "relapse", "pathology", "clinical risk", "manic", "manic episode",
    "clinical_risk"
}

# Normalized tags field name constant
NORMALIZED_TAGS_FIELD = "normalized_tags"
GUMI_WORDS_FIELD = "gumi_words"


class ContinuityService:
    """Service for Shared Continuity Memory operations."""

    def __init__(self):
        self._markers: Dict[str, ContinuityMarker] = {}
        self._followups: Dict[str, ContinuityFollowup] = {}
        self._corrections: Dict[str, ContinuityCorrection] = {}
        self._scopes: Dict[str, Dict[str, Any]] = {}

    def _contains_clinical_term(self, text: str) -> bool:
        """Check if text contains forbidden clinical terms."""
        text_lower = text.lower()
        return any(term in text_lower for term in FORBIDDEN_CLINICAL_TERMS)

    def block_clinicalized_marker(self, normalized_tags: List[str], gumi_words: List[str]) -> None:
        """
        Raise BLOCKED_CLINICALIZATION_IN_MARKER if normalized_tags or gumi_words
        contain forbidden clinical terms.
        """
        forbidden_in_tags = [t for t in normalized_tags if self._contains_clinical_term(t)]
        forbidden_in_words = [w for w in gumi_words if self._contains_clinical_term(w)]

        if forbidden_in_tags:
            raise ContinuityServiceError(
                ContinuityServiceError.BLOCKED_CLINICALIZATION_IN_MARKER,
                f"BLOCKED_CLINICALIZATION_IN_MARKER: Forbidden clinical terms in normalized_tags: {forbidden_in_tags}"
            )
        if forbidden_in_words:
            raise ContinuityServiceError(
                ContinuityServiceError.BLOCKED_CLINICALIZATION_IN_MARKER,
                f"BLOCKED_CLINICALIZATION_IN_MARKER: Forbidden clinical terms in gumi_words: {forbidden_in_words}"
            )

    def normalize_for_gumi(self, normalized_tags: List[str], gumi_words: List[str]) -> tuple[List[str], List[str]]:
        """
        Strip clinical interpretation from tags and words.
        Returns (safe_tags, safe_words) with forbidden clinical terms removed.
        subject_words terms are preserved in input but NOT copied to output.
        """
        safe_tags = [t for t in normalized_tags if not self._contains_clinical_term(t)]
        safe_words = [w for w in gumi_words if not self._contains_clinical_term(w)]
        return safe_tags, safe_words

    def _check_no_clinical_terms_in_normalized_tags(
        self, normalized_tags: List[str], gumi_words: List[str]
    ) -> None:
        """
        Validate that normalized_tags and gumi_words do not contain forbidden clinical terms.
        Raises BLOCKED_CLINICALIZATION_IN_MARKER on violation.
        """
        self.block_clinicalized_marker(normalized_tags, gumi_words)

    def _sanitize_output(
        self,
        marker: ContinuityMarker,
        normalized_tags: Optional[List[str]] = None,
        gumi_words: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Remove any clinical terms from marker output.
        Strips clinical interpretation from normalized_tags and gumi_words before output.
        subject_words (subject's own language) is preserved but NOT copied to other fields.
        """
        # Fallback to marker's persisted values when not explicitly overridden (read-path)
        effective_tags = normalized_tags if normalized_tags is not None else (marker.normalized_tags or [])
        effective_words = gumi_words if gumi_words is not None else (marker.gumi_words or [])
        # Strip clinical terms from normalized_tags and gumi_words for output
        safe_tags, safe_words = self.normalize_for_gumi(
            effective_tags, effective_words
        )

        result = {
            "marker_id": marker.marker_id,
            "subject_id": marker.subject_id,
            "gumi_instance_id": marker.gumi_instance_id,
            "hermes_profile_id": marker.hermes_profile_id,
            "subject_confirmation": marker.subject_confirmation,
            "source_type": marker.source_type,
            "created_at": marker.created_at,
            "subject_words": marker.subject_words,
            "gumi_agreed_words": marker.gumi_agreed_words,
            "status": marker.status.value if isinstance(marker.status, Enum) else marker.status,
            "gumi_recall_allowed": marker.gumi_recall_allowed,
            "recall_count": marker.recall_count,
            "max_recall_count": marker.max_recall_count,
        }

        # Include final_subject_words if available (for authoritative correction recall)
        if marker.final_subject_words is not None:
            result["final_subject_words"] = marker.final_subject_words

        # Only include normalized_tags/gumi_words in output if they are safe (no clinical terms)
        if safe_tags:
            result["normalized_tags"] = safe_tags
        if safe_words:
            result["gumi_words"] = safe_words

        # Verify no clinical terms in output (except subject_words - subject's own language is allowed)
        for key, value in result.items():
            if key == "subject_words":
                continue  # Subject's own words may contain clinical language
            if key in ("normalized_tags", "gumi_words"):
                continue  # Already sanitized above
            if isinstance(value, str) and self._contains_clinical_term(value):
                raise ValueError(f"Clinical term detected in output: {key}")
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, str) and self._contains_clinical_term(item):
                        raise ValueError(f"Clinical term detected in output: {key}")

        return result

    def remember(
        self,
        subject_id: str,
        gumi_instance_id: str,
        hermes_profile_id: str,
        subject_words: List[str],
        source_type: str = "user_confirmed",
        gumi_agreed_words: Optional[List[str]] = None,
        normalized_tags: Optional[List[str]] = None,
        gumi_words: Optional[List[str]] = None,
        max_recall_count: int = 3,
        ttl_seconds: int = 604800,
        *,
        subject_confirmation: bool,
    ) -> Dict[str, Any]:
        """
        Store a subject-confirmed continuity marker.

        subject_confirmation is required (keyword-only, no default): the caller
        must explicitly assert that the subject confirmed this wording. A False
        value is rejected. Inferred observations that the subject has NOT
        confirmed must go through propose_candidate(), not remember().
        Returns the created marker.
        """
        # Verify subject scope
        if not all([subject_id, gumi_instance_id, hermes_profile_id]):
            raise ValueError("BLOCKED_MARKER_WITHOUT_SUBJECT_SCOPE: All scope fields required")

        if not subject_confirmation:
            raise ValueError(
                "BLOCKED_MARKER_WITHOUT_SUBJECT_CONFIRMATION: Subject confirmation required"
            )

        # Clinicalization guard: block forbidden clinical terms in normalized_tags and gumi_words
        if normalized_tags or gumi_words:
            self._check_no_clinical_terms_in_normalized_tags(
                normalized_tags or [],
                gumi_words or []
            )

        # Generate marker ID
        marker_id = f"marker_{subject_id}_{datetime.now().timestamp()}"

        # Calculate expiry
        created_at = datetime.now().isoformat() + "Z"
        expires_at = (datetime.now() + timedelta(seconds=ttl_seconds)).isoformat() + "Z"

        # Create marker only after the caller has supplied explicit confirmation.
        marker = ContinuityMarker(
            marker_id=marker_id,
            subject_id=subject_id,
            gumi_instance_id=gumi_instance_id,
            hermes_profile_id=hermes_profile_id,
            subject_confirmation=True,
            source_type=source_type,
            created_at=created_at,
            subject_words=subject_words,
            gumi_agreed_words=gumi_agreed_words or [],
            raw_source_text=None,
            status=MarkerStatus.ACTIVE,
            gumi_recall_allowed=True,
            recall_count=0,
            max_recall_count=max_recall_count,
            ttl_seconds=ttl_seconds,
            expires_at=expires_at,
            updated_at=created_at,
            normalized_tags=list(normalized_tags) if normalized_tags else None,
            gumi_words=list(gumi_words) if gumi_words else None,
        )

        self._markers[marker_id] = marker

        return self._sanitize_output(marker, normalized_tags, gumi_words)

    def propose_candidate(
        self,
        subject_id: str,
        gumi_instance_id: str,
        hermes_profile_id: str,
        subject_words: List[str],
        source_type: str = "hindsight",
        normalized_tags: Optional[List[str]] = None,
        gumi_words: Optional[List[str]] = None,
        max_recall_count: int = 3,
        ttl_seconds: int = 604800,
    ) -> Dict[str, Any]:
        """
        Store an UNCONFIRMED candidate marker derived from system inference.

        Unlike remember(), this does not claim subject confirmation. The marker
        is created with subject_confirmation=False and candidate_for_confirmation=True,
        so it is excluded from runtime recall (recent_markers) until the subject
        explicitly confirms it. This is the honest path for check-in / hindsight
        inferences that the subject has not yet confirmed in their own words.
        """
        if not all([subject_id, gumi_instance_id, hermes_profile_id]):
            raise ValueError("BLOCKED_MARKER_WITHOUT_SUBJECT_SCOPE: All scope fields required")

        if normalized_tags or gumi_words:
            self._check_no_clinical_terms_in_normalized_tags(
                normalized_tags or [],
                gumi_words or [],
            )

        marker_id = f"candidate_{subject_id}_{datetime.now().timestamp()}"
        created_at = datetime.now().isoformat() + "Z"
        expires_at = (datetime.now() + timedelta(seconds=ttl_seconds)).isoformat() + "Z"

        marker = ContinuityMarker(
            marker_id=marker_id,
            subject_id=subject_id,
            gumi_instance_id=gumi_instance_id,
            hermes_profile_id=hermes_profile_id,
            subject_confirmation=False,
            source_type=source_type,
            created_at=created_at,
            subject_words=subject_words,
            gumi_agreed_words=[],
            raw_source_text=None,
            status=MarkerStatus.ACTIVE,
            gumi_recall_allowed=True,
            recall_count=0,
            max_recall_count=max_recall_count,
            ttl_seconds=ttl_seconds,
            expires_at=expires_at,
            updated_at=created_at,
            normalized_tags=list(normalized_tags) if normalized_tags else None,
            gumi_words=list(gumi_words) if gumi_words else None,
            candidate_for_confirmation=True,
        )

        self._markers[marker_id] = marker

        return self._sanitize_output(marker, normalized_tags, gumi_words)

    def correct(
        self,
        marker_id: str,
        subject_id: str,
        gumi_instance_id: str,
        hermes_profile_id: str,
        subject_words: List[str],
        normalized_tags: Optional[List[str]] = None,
        gumi_words: Optional[List[str]] = None,
        created_by: str = "subject",
    ) -> Dict[str, Any]:
        """
        Mark old marker as corrected and store replacement as authoritative.
        The old marker is NOT selected for Gumi context (gumi_recall_allowed=False).
        The replacement chain is maintained via previous_version_id.
        """
        if marker_id not in self._markers:
            raise ValueError(f"Marker not found: {marker_id}")

        old_marker = self._markers[marker_id]

        # Verify scope matches
        if old_marker.subject_id != subject_id:
            raise ValueError("BLOCKED_CORRECTION_NOT_AUTHORITATIVE: Scope mismatch")

        # Clinicalization guard: block forbidden clinical terms in normalized_tags and gumi_words
        if normalized_tags or gumi_words:
            self._check_no_clinical_terms_in_normalized_tags(
                normalized_tags or [],
                gumi_words or []
            )

        # Create new authoritative marker with replacement chain
        new_marker_id = f"marker_{subject_id}_{datetime.now().timestamp()}"
        created_at = datetime.now().isoformat() + "Z"
        expires_at = (datetime.now() + timedelta(seconds=old_marker.ttl_seconds)).isoformat() + "Z"

        # Mark old marker as corrected - NOT eligible for Gumi context
        old_marker.status = MarkerStatus.CORRECTED
        old_marker.gumi_recall_allowed = False
        old_marker.next_version_id = new_marker_id

        new_marker = ContinuityMarker(
            marker_id=new_marker_id,
            subject_id=subject_id,
            gumi_instance_id=gumi_instance_id,
            hermes_profile_id=hermes_profile_id,
            subject_confirmation=True,
            source_type="subject_corrected",
            created_at=created_at,
            subject_words=subject_words,
            gumi_agreed_words=[],
            raw_source_text=None,
            status=MarkerStatus.ACTIVE,
            gumi_recall_allowed=True,
            recall_count=0,
            max_recall_count=old_marker.max_recall_count,
            ttl_seconds=old_marker.ttl_seconds,
            expires_at=expires_at,
            updated_at=created_at,
            candidate_for_confirmation=False,
            clinical_interpretation_allowed=False,
            previous_version_id=marker_id,
            final_subject_words=subject_words,
            normalized_tags=list(normalized_tags) if normalized_tags else None,
            gumi_words=list(gumi_words) if gumi_words else None,
        )

        self._markers[new_marker_id] = new_marker

        # Create correction record
        correction_id = f"correction_{subject_id}_{datetime.now().timestamp()}"
        correction = ContinuityCorrection(
            correction_id=correction_id,
            marker_id=new_marker_id,
            subject_id=subject_id,
            gumi_instance_id=gumi_instance_id,
            hermes_profile_id=hermes_profile_id,
            authoritative=True,
            subject_words=subject_words,
            gumi_agreed_words=[],
            correction_note=None,
            status="active",
            created_at=created_at,
            created_by=created_by,
            original_marker_id=marker_id,
            is_replacement=True,
        )

        self._corrections[correction_id] = correction

        return {
            "correction_id": correction_id,
            "original_marker_id": marker_id,
            "new_marker_id": new_marker_id,
            "authoritative": True,
            "subject_words": subject_words,
        }

    def due_followups(
        self,
        subject_id: str,
        gumi_instance_id: Optional[str] = None,
        hermes_profile_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Return markers where followup is due and not exhausted.
        Respects pause state and max attempts.
        Excludes markers that are candidates pending confirmation.
        """
        results = []

        for followup_id, followup in self._followups.items():
            # Verify subject scope
            if followup.subject_id != subject_id:
                continue

            if gumi_instance_id and followup.gumi_instance_id != gumi_instance_id:
                continue

            if hermes_profile_id and followup.hermes_profile_id != hermes_profile_id:
                continue

            # Exclude markers that are candidates pending confirmation
            if followup.marker_id in self._markers:
                marker = self._markers[followup.marker_id]
                if marker.candidate_for_confirmation:
                    continue  # BLOCKED_BROAD_MEMORY_CANDIDATE_NOT_IN_GUMI_CONTEXT

            # Check if paused
            if followup.is_paused:
                continue  # BLOCKED_FOLLOWUP_IGNORES_PAUSE

            # Check if exhausted
            if followup.status == FollowupStatus.EXHAUSTED:
                continue

            # Check if expired
            if followup.expires_at:
                if datetime.now() > datetime.fromisoformat(followup.expires_at.replace("Z", "+00:00")):
                    continue  # BLOCKED_FOLLOWUP_IGNORES_TTL

            # Check max attempts
            if followup.attempt_count >= followup.max_attempts:
                continue  # BLOCKED_FOLLOWUP_AFTER_MAX_ATTEMPTS

            # Check if due
            if followup.status in [FollowupStatus.DUE, FollowupStatus.PENDING]:
                results.append({
                    "followup_id": followup_id,
                    "marker_id": followup.marker_id,
                    "subject_id": followup.subject_id,
                    "status": followup.status.value if isinstance(followup.status, Enum) else followup.status,
                    "attempt_count": followup.attempt_count,
                    "max_attempts": followup.max_attempts,
                })

        return results

    def _is_marker_recall_eligible(self, marker: ContinuityMarker) -> bool:
        """
        Check if a marker is recall-eligible per contract:
        - status == ACTIVE
        - expires_at is null OR expires_at > now
        - recall_count < max_recall_count
        - gumi_recall_allowed == true
        - scope not paused
        """
        # Check status == ACTIVE
        if marker.status != MarkerStatus.ACTIVE:
            return False

        # Check expires_at is null OR expires_at > now
        if marker.expires_at:
            try:
                expires_dt = datetime.fromisoformat(marker.expires_at.replace("Z", "+00:00"))
                now = datetime.now(expires_dt.tzinfo) if expires_dt.tzinfo else datetime.now()
                if now > expires_dt:
                    return False
            except (ValueError, TypeError):
                return False

        # Check recall_count < max_recall_count
        if marker.recall_count >= marker.max_recall_count:
            return False

        # Check gumi_recall_allowed == true
        if not marker.gumi_recall_allowed:
            return False

        # Check scope not paused
        scope_key = f"{marker.subject_id}:{marker.gumi_instance_id}:{marker.hermes_profile_id}:global"
        if self._scopes.get(scope_key, {}).get("is_paused", False):
            return False

        return True

    def is_confirmation_candidate(self, marker_id: str) -> bool:
        """
        Check if a marker is an unconfirmed Hindsight/broad-memory candidate.
        Returns True if candidate_for_confirmation is True.
        """
        if marker_id not in self._markers:
            return False
        return self._markers[marker_id].candidate_for_confirmation

    def get_descriptive_summary_markers(
        self,
        subject_id: str,
        gumi_instance_id: Optional[str] = None,
        hermes_profile_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Return markers eligible for descriptive summaries.

        Filters for:
        - source_type in: subject_confirmed, subject_requested, subject_corrected
        - clinical_interpretation_allowed = False
        - status != rejected
        - status != forgotten
        - gumi_recall_allowed = True

        Excludes:
        - safety signals (source_type=hindsight_safety_signal)
        - unconfirmed candidates (candidate_for_confirmation=True)
        - researcher-only notes (source_type=researcher_only_note)
        - clinical tags (clinical_interpretation_allowed=True)
        - hidden evidence (gumi_recall_allowed=False)
        """
        valid_source_types = {"subject_confirmed", "subject_requested", "subject_corrected"}

        results = []

        for marker_id, marker in self._markers.items():
            # Verify subject scope
            if marker.subject_id != subject_id:
                continue

            if gumi_instance_id and marker.gumi_instance_id != gumi_instance_id:
                continue

            if hermes_profile_id and marker.hermes_profile_id != hermes_profile_id:
                continue

            # source_type must be one of the subject-confirmed types
            if marker.source_type not in valid_source_types:
                continue

            # clinical_interpretation_allowed must be False
            if marker.clinical_interpretation_allowed:
                continue

            # status must not be rejected
            if marker.status == MarkerStatus.REJECTED:
                continue

            # status must not be forgotten
            if marker.status == MarkerStatus.FORGOTTEN:
                continue

            # gumi_recall_allowed must be True
            if not marker.gumi_recall_allowed:
                continue

            # Exclude unconfirmed candidates
            if marker.candidate_for_confirmation:
                continue

            results.append(self._sanitize_output(marker))

        # Sort by created_at descending
        results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return results

    def _get_latest_authoritative_marker(self, marker: ContinuityMarker) -> ContinuityMarker:
        """
        Traverse replacement chain to find the latest authoritative marker.
        Returns the latest marker in the chain, or the given marker if no replacement.
        """
        current = marker
        while current.next_version_id and current.next_version_id in self._markers:
            current = self._markers[current.next_version_id]
        return current

    def recent_markers(
        self,
        subject_id: str,
        gumi_instance_id: Optional[str] = None,
        hermes_profile_id: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Return subject-confirmed markers only.
        Only returns recall-eligible markers per contract.
        Excludes candidates marked candidate_for_confirmation=True.
        Resolves to latest authoritative marker when replacement chain exists.
        """
        results = []
        seen_authoritative_ids = set()

        for marker_id, marker in self._markers.items():
            # Verify subject scope
            if marker.subject_id != subject_id:
                continue

            if gumi_instance_id and marker.gumi_instance_id != gumi_instance_id:
                continue

            if hermes_profile_id and marker.hermes_profile_id != hermes_profile_id:
                continue

            # Only confirmed markers
            if not marker.subject_confirmation:
                continue  # BLOCKED_UNCONFIRMED_MARKER_RECALLED

            if marker.source_type in FORBIDDEN_RUNTIME_SOURCE_TYPES:
                continue

            if marker.source_type not in RUNTIME_RECALL_SOURCE_TYPES:
                continue

            # Exclude candidates pending confirmation
            if marker.candidate_for_confirmation:
                continue  # BLOCKED_BROAD_MEMORY_CANDIDATE_NOT_IN_GUMI_CONTEXT

            # Check recall eligibility (includes status, TTL, recall count, permission, scope)
            if not self._is_marker_recall_eligible(marker):
                continue

            # Resolve to latest authoritative marker in replacement chain
            latest_marker = self._get_latest_authoritative_marker(marker)

            # Skip if we've already included this authoritative marker
            if latest_marker.marker_id in seen_authoritative_ids:
                continue
            seen_authoritative_ids.add(latest_marker.marker_id)

            results.append(self._sanitize_output(latest_marker))

        # Sort by created_at descending
        results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return results[:limit]

    def forget(
        self,
        marker_id: str,
        subject_id: str,
    ) -> Dict[str, Any]:
        """
        Remove from Gumi recall without deleting from storage.
        """
        if marker_id not in self._markers:
            raise ValueError(f"Marker not found: {marker_id}")

        marker = self._markers[marker_id]

        if marker.subject_id != subject_id:
            raise ValueError("Subject scope mismatch")

        # Remove from Gumi recall
        marker.gumi_recall_allowed = False

        return {
            "marker_id": marker_id,
            "forgotten": True,
            "gumi_recall_allowed": False,
        }

    def forget_subject(self, subject_id: str) -> Dict[str, Any]:
        """GDPR Art. 17 hard delete — remove all in-memory data for subject_id.

        Covers markers, followups, corrections, and scopes. Does NOT touch
        filesystem or SQLite — callers must also invoke
        chronicle.retention.purge_subject_records() and
        ProfileRegistry.delete_subject() for a complete GDPR erasure.
        """
        marker_ids = [k for k, m in self._markers.items() if m.subject_id == subject_id]
        for k in marker_ids:
            del self._markers[k]

        followup_ids = [k for k, f in self._followups.items() if f.subject_id == subject_id]
        for k in followup_ids:
            del self._followups[k]

        correction_ids = [k for k, c in self._corrections.items() if c.subject_id == subject_id]
        for k in correction_ids:
            del self._corrections[k]

        scope_keys = [k for k, s in self._scopes.items() if s.get("subject_id") == subject_id]
        for k in scope_keys:
            del self._scopes[k]

        return {
            "subject_id": subject_id,
            "markers_removed": len(marker_ids),
            "followups_removed": len(followup_ids),
            "corrections_removed": len(correction_ids),
            "scopes_removed": len(scope_keys),
        }

    def pause(
        self,
        subject_id: str,
        scope_name: str = "global",
        gumi_instance_id: Optional[str] = None,
        hermes_profile_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Block follow-ups from paused scope.
        """
        scope_key = f"{subject_id}:{gumi_instance_id}:{hermes_profile_id}:{scope_name}"

        self._scopes[scope_key] = {
            "is_paused": True,
            "paused_at": datetime.now().isoformat() + "Z",
            "subject_id": subject_id,
            "gumi_instance_id": gumi_instance_id,
            "hermes_profile_id": hermes_profile_id,
            "scope_name": scope_name,
        }

        return {
            "subject_id": subject_id,
            "scope_name": scope_name,
            "is_paused": True,
            "paused_at": self._scopes[scope_key]["paused_at"],
        }

    def resume(
        self,
        subject_id: str,
        scope_name: str = "global",
        gumi_instance_id: Optional[str] = None,
        hermes_profile_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Restore follow-ups.
        """
        scope_key = f"{subject_id}:{gumi_instance_id}:{hermes_profile_id}:{scope_name}"

        if scope_key in self._scopes:
            self._scopes[scope_key]["is_paused"] = False
            self._scopes[scope_key]["resumed_at"] = datetime.now().isoformat() + "Z"

        return {
            "subject_id": subject_id,
            "scope_name": scope_name,
            "is_paused": False,
            "resumed_at": datetime.now().isoformat() + "Z",
        }


# Global service instance
_service = ContinuityService()


def get_continuity_service() -> ContinuityService:
    """Get the global continuity service instance."""
    return _service


# ---------------------------------------------------------------------------
# Proactive queue producer (Plan §Task 9)
# ---------------------------------------------------------------------------


def _proactive_queue_path(subject_id: str, relic_home: Optional[str] = None):
    """Return the per-subject proactive queue JSONL path.

    Lazily imported so this module stays cheap to load.
    """
    import os
    from pathlib import Path as _Path

    home = _Path(relic_home or os.environ.get("RELIC_HOME") or _Path.home() / ".relic")
    return home / "subjects" / subject_id / "proactive_queue.jsonl"


def enqueue_proactive_candidate(
    *,
    subject_id: str,
    signal_ref: str,
    suggested_posture: str = "brief_share",
    priority: float = 0.5,
    expires_at: Optional[str] = None,
    dedupe_key: Optional[str] = None,
    relic_home: Optional[str] = None,
) -> Dict[str, Any]:
    """Append a ProactiveCandidate record to the per-subject queue.

    Spike §11.3 shape:
        {"id": "...", "signal_ref": "...", "suggested_posture": "...",
         "expires_at": "...", "priority": 0.6, "enqueued_at": "...",
         "dedupe_key": "..."}

    Dedupe: when ``dedupe_key`` is provided and matches an unconsumed entry,
    the existing entry is returned and no new row is appended.
    Returns the candidate dict that now lives at the head of the queue.
    """
    import json as _json
    import uuid as _uuid
    from datetime import datetime as _dt, timezone as _tz

    path = _proactive_queue_path(subject_id, relic_home)
    path.parent.mkdir(parents=True, exist_ok=True)

    now = _dt.now(_tz.utc)
    candidate: Dict[str, Any] = {
        "id": f"pc-{_uuid.uuid4().hex[:12]}",
        "subject_id": subject_id,
        "signal_ref": signal_ref,
        "suggested_posture": suggested_posture,
        "priority": float(priority),
        "expires_at": expires_at,
        "enqueued_at": now.isoformat(),
        "dedupe_key": dedupe_key,
    }

    existing: list[Dict[str, Any]] = []
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        existing.append(_json.loads(line))
                    except _json.JSONDecodeError:
                        continue
        except OSError:
            existing = []

    if dedupe_key:
        for row in existing:
            if row.get("dedupe_key") == dedupe_key and not row.get("consumed_at"):
                return row

    with open(path, "a", encoding="utf-8") as fh:
        fh.write(_json.dumps(candidate) + "\n")
    return candidate
