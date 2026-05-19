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


REACH_THRESHOLD = 0.35
PROACTIVE_SALIENCE_THRESHOLD = 0.6
REFLECT_THRESHOLD = 0.8
BRIEF_SHARE_THRESHOLD = 0.4
TOPIC_FRESHNESS_FOR_ASK = 0.6
MID_CONVERSATION_SECONDS = 120
NON_RESPONSE_BACKOFF = 3
ASK_COOLDOWN_HOURS = 12
REFLECT_COOLDOWN_DAYS = 7
BRIEF_SHARE_MIN_AVG_TOKENS = 10.0


def _last_posture(features: CheckinFeatures) -> Optional[str]:
    if not features.posture_history_last_5:
        return None
    return features.posture_history_last_5[0]


def select_decision(
    features: CheckinFeatures,
    *,
    decision_type: str,
    policy_enabled: bool = False,
    reflection_enabled: bool = False,
) -> Decision:
    """Spike §9.2 decision tree (deterministic, replayable).

    Returns silent until ``policy_enabled`` flips true so this can land behind
    a flag without behavior change. Reflection requires explicit opt-in via
    ``reflection_enabled`` (spike §15 conservative default).
    """

    if features.risk_flag_active:
        return Decision(EventType.SILENT, Posture.QUIET, "risk_flag_active")

    if not features.consent_active:
        return Decision(EventType.SILENT, Posture.QUIET, "consent_inactive")

    if not policy_enabled:
        return Decision(EventType.SILENT, Posture.QUIET, "policy_disabled")

    if features.quiet_hours_active:
        return Decision(EventType.SILENT, Posture.QUIET, "quiet_hours")

    if (
        features.frequency_cap_per_day is not None
        and features.daily_initiatives_today >= features.frequency_cap_per_day
    ):
        return Decision(EventType.SILENT, Posture.QUIET, "frequency_cap_reached")

    if features.reach_score < REACH_THRESHOLD:
        return Decision(EventType.SILENT, Posture.QUIET, "reach_below_threshold")

    if (
        features.time_since_last_subject_msg_sec is not None
        and features.time_since_last_subject_msg_sec < MID_CONVERSATION_SECONDS
    ):
        return Decision(EventType.SILENT, Posture.QUIET, "mid_conversation")

    if decision_type == "followup":
        if features.non_response_streak == 0:
            return Decision(EventType.FOLLOWUP, Posture.FOLLOW_UP_WARM, "followup_first_attempt")
        return Decision(EventType.FOLLOWUP, Posture.FOLLOW_UP_TERSE, "followup_after_silence")

    if decision_type == "proactivity":
        if features.non_response_streak >= NON_RESPONSE_BACKOFF:
            return Decision(EventType.SILENT, Posture.QUIET, "proactive_backoff")
        if features.salience_top > PROACTIVE_SALIENCE_THRESHOLD:
            return Decision(EventType.PROACTIVE, Posture.BRIEF_SHARE, "proactive_salient")
        return Decision(EventType.SILENT, Posture.QUIET, "proactive_below_salience")

    # decision_type == "checkin"
    if features.non_response_streak >= NON_RESPONSE_BACKOFF:
        return Decision(EventType.SILENT, Posture.QUIET, "non_response_backoff")

    if (
        features.importance_accumulator > REFLECT_THRESHOLD
        and (features.last_reflect_age_days is None or features.last_reflect_age_days >= REFLECT_COOLDOWN_DAYS)
    ):
        if not reflection_enabled:
            return Decision(EventType.SILENT, Posture.QUIET, "reflection_disabled")
        return Decision(EventType.REFLECTION, Posture.REFLECTIVE_MIRROR, "reflect_threshold_met")

    if (
        features.topic_freshness > TOPIC_FRESHNESS_FOR_ASK
        and features.facet_status == "ask_now"
        and not features.asked_recently_12h
        and _last_posture(features) != Posture.ASK.value
    ):
        return Decision(EventType.CHECKIN, Posture.ASK, "topic_fresh_and_ask_ready")

    if features.salience_top > BRIEF_SHARE_THRESHOLD:
        avg = features.subject_avg_tokens_14d
        if avg is None or avg >= BRIEF_SHARE_MIN_AVG_TOKENS:
            return Decision(EventType.CHECKIN, Posture.BRIEF_SHARE, "salient_brief_share")
        # subject is laconic → forbidden brief_share, fall through to observe.

    return Decision(EventType.CHECKIN, Posture.OBSERVE, "default_observe")
