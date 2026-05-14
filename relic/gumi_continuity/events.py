"""Events for Gumi Continuity (PR06).

Event types for tracking continuity-related actions:
- Recall events
- Admission events
- Correction events
- Pause/resume events
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum


class ContinuityEventType(str, Enum):
    """Types of continuity events."""
    RECALL = "continuity_recall"
    ADMISSION = "continuity_admission"
    CORRECTION = "continuity_correction"
    PAUSE = "continuity_pause"
    RESUME = "continuity_resume"
    CREATED = "continuity_created"
    FORGOTTEN = "continuity_forgotten"


@dataclass
class ContinuityRecallEvent:
    """Event emitted when a continuity marker is recalled."""
    event_id: str
    marker_id: str
    subject_id: str
    gumi_instance_id: str
    hermes_profile_id: str
    recall_count_before: int
    recall_count_after: int
    admitted: bool
    blocked_by: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": ContinuityEventType.RECALL.value,
            "event_id": self.event_id,
            "marker_id": self.marker_id,
            "subject_id": self.subject_id,
            "gumi_instance_id": self.gumi_instance_id,
            "hermes_profile_id": self.hermes_profile_id,
            "recall_count_before": self.recall_count_before,
            "recall_count_after": self.recall_count_after,
            "admitted": self.admitted,
            "blocked_by": self.blocked_by,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class ContinuityAdmissionEvent:
    """Event emitted when a continuity marker is evaluated for admission."""
    event_id: str
    marker_id: str
    subject_id: str
    admitted: bool
    blocked_by: Optional[str] = None
    reason: str = ""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": ContinuityEventType.ADMISSION.value,
            "event_id": self.event_id,
            "marker_id": self.marker_id,
            "subject_id": self.subject_id,
            "admitted": self.admitted,
            "blocked_by": self.blocked_by,
            "reason": self.reason,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class ContinuityCorrectionEvent:
    """Event emitted when a continuity marker is corrected."""
    event_id: str
    marker_id: str
    new_marker_id: str
    subject_id: str
    gumi_instance_id: str
    hermes_profile_id: str
    old_subject_words: List[str]
    new_subject_words: List[str]
    authoritative: bool
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": ContinuityEventType.CORRECTION.value,
            "event_id": self.event_id,
            "marker_id": self.marker_id,
            "new_marker_id": self.new_marker_id,
            "subject_id": self.subject_id,
            "gumi_instance_id": self.gumi_instance_id,
            "hermes_profile_id": self.hermes_profile_id,
            "old_subject_words": self.old_subject_words,
            "new_subject_words": self.new_subject_words,
            "authoritative": self.authoritative,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class ContinuityPauseEvent:
    """Event emitted when continuity recall is paused for a scope."""
    event_id: str
    subject_id: str
    gumi_instance_id: Optional[str]
    hermes_profile_id: Optional[str]
    scope_name: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": ContinuityEventType.PAUSE.value,
            "event_id": self.event_id,
            "subject_id": self.subject_id,
            "gumi_instance_id": self.gumi_instance_id,
            "hermes_profile_id": self.hermes_profile_id,
            "scope_name": self.scope_name,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class ContinuityResumeEvent:
    """Event emitted when continuity recall is resumed for a scope."""
    event_id: str
    subject_id: str
    gumi_instance_id: Optional[str]
    hermes_profile_id: Optional[str]
    scope_name: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": ContinuityEventType.RESUME.value,
            "event_id": self.event_id,
            "subject_id": self.subject_id,
            "gumi_instance_id": self.gumi_instance_id,
            "hermes_profile_id": self.hermes_profile_id,
            "scope_name": self.scope_name,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }
