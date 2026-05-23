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
    DIEGETIC = "diegetic"
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
    time_since_last_initiative_sec: Optional[int] = None
    last_delivered_initiative_at: Optional[datetime] = None
    last_subject_msg_at: Optional[datetime] = None

    salience_top: float = 0.0
    topic_freshness: float = 1.0
    importance_accumulator: float = 0.0
    continuity_preference: float = 0.5
    comfort_with_initiative: float = 0.5
    diegetic_enabled: bool = False
    diegetic_tolerance: float = 0.45
    diegetic_intensity: Optional[float] = None
    diegetic_frequency: Optional[float] = None

    subject_avg_tokens_14d: Optional[float] = None
    facet_status: Optional[str] = None
    asked_recently_12h: bool = False
    last_reflect_age_days: Optional[int] = None

    posture_history_last_5: list[str] = field(default_factory=list)

    frequency_cap_per_day: Optional[int] = None
    daily_initiatives_today: int = 0
    diegetic_today: int = 0
    proactive_today: int = 0
    quiet_hours_active: bool = False
    current_checkin_slot: Optional[str] = None
    enabled_checkin_slots: list[str] = field(default_factory=list)
    used_checkin_slots_today: list[str] = field(default_factory=list)


@dataclass
class Decision:
    event_type: EventType
    posture: Posture
    reason: str
    constraints: dict = field(default_factory=dict)


_POSTURE_MAX_SENTENCES: dict[Posture, int] = {
    Posture.QUIET: 0,
    Posture.OBSERVE: 1,
    Posture.BRIEF_SHARE: 2,
    Posture.ASK: 2,
    Posture.FOLLOW_UP_WARM: 3,
    Posture.FOLLOW_UP_TERSE: 2,
    Posture.REFLECTIVE_MIRROR: 2,
    Posture.SMALL_SHARE: 1,
    Posture.REPAIR: 2,
}

_POSTURES_WITH_QUESTION = {Posture.ASK}


def posture_max_sentences(posture: Posture) -> int:
    return _POSTURE_MAX_SENTENCES.get(posture, 2)


def posture_requires_question(posture: Posture) -> bool:
    return posture in _POSTURES_WITH_QUESTION


def render_constraint_header(
    event_type: EventType | str,
    posture: Posture | str,
    *,
    max_sentences: Optional[int] = None,
    with_question: Optional[bool] = None,
    grounding: Optional[str] = None,
) -> str:
    """Return the deterministic ``[EVENTO:][POSTURA:][VINCOLI:][GROUNDING:]`` header.

    Spike §10.1. Single source of truth for what the composer LLM sees as
    behavioural constraints — both posture and per-posture sentence cap.
    Returns an empty string for silent events so the caller can no-op.
    """
    if isinstance(event_type, EventType):
        ev = event_type.value
    else:
        ev = str(event_type or "")
    if isinstance(posture, Posture):
        ps = posture
        ps_str = posture.value
    else:
        ps_str = str(posture or "")
        try:
            ps = Posture(ps_str)
        except ValueError:
            ps = Posture.QUIET

    if ev == EventType.SILENT.value or ps_str == Posture.QUIET.value:
        return ""

    if max_sentences is None:
        max_sentences = posture_max_sentences(ps)
    if with_question is None:
        with_question = posture_requires_question(ps)

    domanda = "con domanda" if with_question else "senza domanda"
    lines = [
        f"[EVENTO: {ev}]",
        f"[POSTURA: {ps_str}]",
        f"[VINCOLI: max {max_sentences} frasi; {domanda}]",
    ]
    if grounding:
        grounding = grounding.replace("\n", " ").strip()
        if grounding:
            lines.append(f"[GROUNDING: {grounding[:200]}]")
    return "\n".join(lines) + "\n"


def apply_constraint_header(
    message: str,
    decision: Decision,
    *,
    grounding: Optional[str] = None,
) -> str:
    """Prepend the constraint header to ``message`` for non-silent decisions."""
    header = render_constraint_header(
        decision.event_type,
        decision.posture,
        grounding=grounding,
    )
    if not header:
        return message
    return f"{header}{message}"


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
MIN_INITIATIVE_GAP_HOURS = 4
DIEGETIC_MAX_PER_DAY = 1
PROACTIVE_MAX_PER_DAY = 1


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _effective_checkin_thresholds(cp: float) -> tuple[float, float, int]:
    topic_freshness_for_ask = _clamp(
        TOPIC_FRESHNESS_FOR_ASK - 0.3 * (cp - 0.5),
        0.2,
        0.9,
    )
    reflect_threshold = _clamp(
        REFLECT_THRESHOLD - 0.3 * (cp - 0.5),
        0.4,
        0.95,
    )
    reflect_cooldown_days = max(
        1,
        round(REFLECT_COOLDOWN_DAYS - 6.0 * (cp - 0.5)),
    )
    return topic_freshness_for_ask, reflect_threshold, reflect_cooldown_days


assert _effective_checkin_thresholds(0.5) == (
    TOPIC_FRESHNESS_FOR_ASK,
    REFLECT_THRESHOLD,
    REFLECT_COOLDOWN_DAYS,
)


def _effective_proactive_threshold(comfort_with_initiative: float) -> float:
    return _clamp(
        PROACTIVE_SALIENCE_THRESHOLD + 0.3 * (0.5 - comfort_with_initiative),
        PROACTIVE_SALIENCE_THRESHOLD,
        0.95,
    )


assert _effective_proactive_threshold(0.5) == PROACTIVE_SALIENCE_THRESHOLD


def _last_posture(features: CheckinFeatures) -> Optional[str]:
    if not features.posture_history_last_5:
        return None
    return features.posture_history_last_5[0]


def _enabled_checkin_slots(features: CheckinFeatures) -> set[str]:
    return {str(slot).strip().lower() for slot in features.enabled_checkin_slots if str(slot).strip()}


def _used_checkin_slots(features: CheckinFeatures) -> set[str]:
    return {str(slot).strip().lower() for slot in features.used_checkin_slots_today if str(slot).strip()}


def _current_checkin_slot(features: CheckinFeatures) -> Optional[str]:
    if not features.current_checkin_slot:
        return None
    return str(features.current_checkin_slot).strip().lower() or None


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
    eff_topic_freshness_for_ask, eff_reflect_threshold, eff_reflect_cooldown_days = (
        _effective_checkin_thresholds(features.continuity_preference)
    )

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

    if (
        features.time_since_last_initiative_sec is not None
        and features.time_since_last_initiative_sec < MIN_INITIATIVE_GAP_HOURS * 3600
    ):
        return Decision(EventType.SILENT, Posture.QUIET, "initiative_spacing")

    enabled_slots = _enabled_checkin_slots(features)
    current_slot = _current_checkin_slot(features)
    used_slots = _used_checkin_slots(features)

    if decision_type == "checkin" and enabled_slots:
        if current_slot not in enabled_slots:
            return Decision(EventType.SILENT, Posture.QUIET, "checkin_slot_disabled")
        if current_slot in used_slots:
            return Decision(EventType.SILENT, Posture.QUIET, "checkin_slot_already_used")

    if decision_type in {"diegetic", "proactivity"} and enabled_slots:
        if current_slot in enabled_slots and current_slot not in used_slots:
            return Decision(EventType.SILENT, Posture.QUIET, "reserved_checkin_slot")

    if decision_type == "diegetic":
        if not features.diegetic_enabled:
            return Decision(EventType.SILENT, Posture.QUIET, "diegetic_disabled")
        if features.diegetic_today >= DIEGETIC_MAX_PER_DAY:
            return Decision(EventType.SILENT, Posture.QUIET, "diegetic_daily_cap")
        if (
            features.diegetic_frequency is not None
            and features.diegetic_frequency < 0.25
        ):
            return Decision(EventType.SILENT, Posture.QUIET, "diegetic_frequency_backoff")
        if features.diegetic_tolerance >= 0.5:
            if features.diegetic_intensity is None:
                return Decision(EventType.DIEGETIC, Posture.SMALL_SHARE, "diegetic_share")
            if features.diegetic_intensity < 0.5:
                return Decision(
                    EventType.DIEGETIC,
                    Posture.SMALL_SHARE,
                    "diegetic_share_factual",
                )
            return Decision(
                EventType.DIEGETIC,
                Posture.BRIEF_SHARE,
                "diegetic_share_warm",
            )
        return Decision(EventType.SILENT, Posture.QUIET, "diegetic_below_tolerance")

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
        if features.proactive_today >= PROACTIVE_MAX_PER_DAY:
            return Decision(EventType.SILENT, Posture.QUIET, "proactive_daily_cap")
        if features.non_response_streak >= NON_RESPONSE_BACKOFF:
            return Decision(EventType.SILENT, Posture.QUIET, "proactive_backoff")
        if features.comfort_with_initiative < 0.2:
            return Decision(EventType.SILENT, Posture.QUIET, "proactive_low_receptivity")
        eff_proactive_threshold = _effective_proactive_threshold(features.comfort_with_initiative)
        if features.salience_top > eff_proactive_threshold:
            # Spike §9.5 forbidden transition: no brief_share when subject is laconic.
            avg = features.subject_avg_tokens_14d
            if avg is not None and avg < BRIEF_SHARE_MIN_AVG_TOKENS:
                return Decision(EventType.SILENT, Posture.QUIET, "proactive_subject_laconic")
            return Decision(EventType.PROACTIVE, Posture.BRIEF_SHARE, "proactive_salient")
        return Decision(EventType.SILENT, Posture.QUIET, "proactive_below_salience")

    # decision_type == "checkin"
    if features.non_response_streak >= NON_RESPONSE_BACKOFF:
        return Decision(EventType.SILENT, Posture.QUIET, "non_response_backoff")

    if (
        features.importance_accumulator > eff_reflect_threshold
        and (
            features.last_reflect_age_days is None
            or features.last_reflect_age_days >= eff_reflect_cooldown_days
        )
    ):
        if not reflection_enabled:
            return Decision(EventType.SILENT, Posture.QUIET, "reflection_disabled")
        return Decision(EventType.REFLECTION, Posture.REFLECTIVE_MIRROR, "reflect_threshold_met")

    # Spike §9.5: forbid ask→ask only when the previous ask got no reply.
    _last = _last_posture(features)
    ask_blocked_by_streak = _last == Posture.ASK.value and features.non_response_streak >= 1
    if (
        features.topic_freshness > eff_topic_freshness_for_ask
        and features.facet_status == "ask_now"
        and not features.asked_recently_12h
        and not ask_blocked_by_streak
    ):
        return Decision(EventType.CHECKIN, Posture.ASK, "topic_fresh_and_ask_ready")

    return Decision(EventType.SILENT, Posture.QUIET, "checkin_no_facet_target")
