"""Cron check-in policy layer.

Pure-function selector that turns a CheckinFeatures vector and a decision_type
into a Decision (EventType, Posture, reason). Implements the spike §9 model:
posture is the decision; the message is its rendering; silence is a first-class
output.

This module is intentionally side-effect free. Persistence happens upstream in
relic.checkin.features.persist_features and downstream in cron_wiring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class EventType(str, Enum):
    SILENT = "silent"
    CHECKIN = "checkin"
    FOLLOWUP = "followup"
    PROACTIVE = "proactive"
    REMINDER = "reminder"
    REFLECTION = "reflection"


class Posture(str, Enum):
    QUIET = "quiet"
    OBSERVE = "observe"
    BRIEF_SHARE = "brief_share"
    ASK = "ask"
    FOLLOW_UP_WARM = "follow_up_warm"
    FOLLOW_UP_TERSE = "follow_up_terse"
    REFLECTIVE_MIRROR = "reflective_mirror"
    SMALL_SHARE = "small_share"
    REPAIR = "repair"


@dataclass
class CheckinFeatures:
    """Inspectable feature vector consumed by select_decision.

    Defaults are conservative so that an empty vector falls through to silent.
    Populated by relic.checkin.features.build_checkin_features().
    """

    subject_id: Optional[str] = None
    risk_flag_active: bool = False
    consent_active: bool = True
    boundary_strict: bool = False

    reach_score: float = 1.0
    non_response_streak: int = 0
    followup_non_response_streak: int = 0
    time_since_last_subject_msg_sec: Optional[int] = None
    last_delivered_initiative_at: Optional[datetime] = None
    last_subject_msg_at: Optional[datetime] = None

    salience_top: float = 0.0
    topic_freshness: float = 1.0
    importance_accumulator: float = 0.0

    subject_avg_tokens_14d: Optional[float] = None
    facet_status: Optional[str] = None
    asked_recently_12h: bool = False
    last_reflect_age_days: Optional[int] = None

    posture_history_last_5: list[str] = field(default_factory=list)

    frequency_cap_per_day: Optional[int] = None
    daily_initiatives_today: int = 0
    quiet_hours_active: bool = False


@dataclass
class Decision:
    event_type: EventType
    posture: Posture
    reason: str
    constraints: dict = field(default_factory=dict)


def select_decision(
    features: CheckinFeatures,
    *,
    decision_type: str,
    policy_enabled: bool = False,
    reflection_enabled: bool = False,
) -> Decision:
    """Select an (event_type, posture) for the current tick.

    Conservative defaults: risk flag or policy disabled → silent. Real thresholds
    land in Task 5; this stub keeps everything downstream observable and safe.
    """

    if features.risk_flag_active:
        return Decision(EventType.SILENT, Posture.QUIET, "risk_flag_active")

    if not features.consent_active:
        return Decision(EventType.SILENT, Posture.QUIET, "consent_inactive")

    if not policy_enabled:
        return Decision(EventType.SILENT, Posture.QUIET, "policy_disabled")

    # Task 5 fills in the thresholded decision tree; until then, default silent.
    return Decision(EventType.SILENT, Posture.QUIET, "policy_stub_default")
