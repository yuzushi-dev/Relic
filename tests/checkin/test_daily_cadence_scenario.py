"""End-to-end-ish scenario for the intended daily cadence.

Models the subject configuration we ship for a morning/evening subject
(check-in slots = morning + evening, diegetic enabled, daily cap = 4) and walks
``select_decision``, the real arbiter behind the no-agent cron, through a day
to prove the target pattern:

    morning  → check-in (1)
    afternoon→ diegetic (2) then proactive (3), spaced ≥ MIN_INITIATIVE_GAP_HOURS
    evening  → check-in (4)

and that diegetic/proactive never land in a reserved check-in slot, that the
inter-initiative spacing prevents bunching, and that the daily cap stops a 5th.
"""

from __future__ import annotations

from relic.checkin.policy import (
    DIEGETIC_MAX_PER_DAY,
    MIN_INITIATIVE_GAP_HOURS,
    PROACTIVE_MAX_PER_DAY,
    CheckinFeatures,
    EventType,
    select_decision,
)

ENABLED_SLOTS = ["morning", "evening"]
DAILY_CAP = 4


def _features(
    *,
    slot: str,
    used_slots: list[str],
    daily_total: int,
    diegetic_today: int = 0,
    proactive_today: int = 0,
    time_since_last_initiative_sec: int | None = None,
    facet_ready: bool = True,
) -> CheckinFeatures:
    """Build a feature vector for a morning/evening subject at a given tick."""
    return CheckinFeatures(
        reach_score=1.0,
        salience_top=0.9,
        comfort_with_initiative=0.9,
        time_since_last_subject_msg_sec=7200,
        time_since_last_initiative_sec=time_since_last_initiative_sec,
        frequency_cap_per_day=DAILY_CAP,
        daily_initiatives_today=daily_total,
        diegetic_enabled=True,
        diegetic_tolerance=0.9,
        diegetic_today=diegetic_today,
        proactive_today=proactive_today,
        subject_avg_tokens_14d=40.0,
        current_checkin_slot=slot,
        enabled_checkin_slots=ENABLED_SLOTS,
        used_checkin_slots_today=used_slots,
        facet_status="ask_now" if facet_ready else None,
        asked_recently_12h=not facet_ready,
        topic_freshness=0.9,
    )


def _decide(decision_type: str, **kwargs):
    return select_decision(
        _features(**kwargs),
        decision_type=decision_type,
        policy_enabled=True,
    )


def test_morning_slot_delivers_checkin_and_reserves_against_ambient():
    common = dict(slot="morning", used_slots=[], daily_total=0)
    assert _decide("checkin", **common).event_type is EventType.CHECKIN
    # Ambient initiatives must not steal the morning check-in slot…
    assert _decide("diegetic", **common).reason == "reserved_checkin_slot"
    assert _decide("proactivity", **common).reason == "reserved_checkin_slot"


def test_morning_slot_stays_reserved_even_after_checkin_used():
    # Regression: previously diegetic could fire in the morning slot once the
    # check-in had been delivered, gluing it to the check-in.
    used = dict(slot="morning", used_slots=["morning"], daily_total=1)
    assert _decide("diegetic", **used).reason == "reserved_checkin_slot"
    assert _decide("proactivity", **used).reason == "reserved_checkin_slot"


def test_afternoon_fills_with_diegetic_then_proactive_when_spaced():
    long_gap = (MIN_INITIATIVE_GAP_HOURS + 1) * 3600
    # After the morning check-in, the afternoon is the residual slot.
    diegetic = _decide(
        "diegetic",
        slot="afternoon",
        used_slots=["morning"],
        daily_total=1,
        time_since_last_initiative_sec=long_gap,
    )
    assert diegetic.event_type is EventType.DIEGETIC

    proactive = _decide(
        "proactivity",
        slot="afternoon",
        used_slots=["morning"],
        daily_total=2,
        diegetic_today=1,
        time_since_last_initiative_sec=long_gap,
    )
    assert proactive.event_type is EventType.PROACTIVE


def test_afternoon_spacing_blocks_bunching():
    short_gap = (MIN_INITIATIVE_GAP_HOURS * 3600) - 60  # just inside the gap
    blocked = _decide(
        "proactivity",
        slot="afternoon",
        used_slots=["morning"],
        daily_total=2,
        diegetic_today=1,
        time_since_last_initiative_sec=short_gap,
    )
    assert blocked.event_type is EventType.SILENT
    assert blocked.reason == "initiative_spacing"


def test_evening_slot_delivers_second_checkin():
    long_gap = (MIN_INITIATIVE_GAP_HOURS + 1) * 3600
    evening = _decide(
        "checkin",
        slot="evening",
        used_slots=["morning"],
        daily_total=3,
        diegetic_today=1,
        proactive_today=1,
        time_since_last_initiative_sec=long_gap,
        facet_ready=True,
    )
    assert evening.event_type is EventType.CHECKIN


def test_daily_cap_stops_a_fifth_initiative():
    long_gap = (MIN_INITIATIVE_GAP_HOURS + 1) * 3600
    capped = _decide(
        "diegetic",
        slot="afternoon",
        used_slots=["morning", "evening"],
        daily_total=DAILY_CAP,
        diegetic_today=DIEGETIC_MAX_PER_DAY,
        proactive_today=PROACTIVE_MAX_PER_DAY,
        time_since_last_initiative_sec=long_gap,
    )
    assert capped.event_type is EventType.SILENT
    assert capped.reason == "frequency_cap_reached"


def test_per_type_caps_hold_within_residual_slot():
    long_gap = (MIN_INITIATIVE_GAP_HOURS + 1) * 3600
    assert (
        _decide(
            "diegetic",
            slot="afternoon",
            used_slots=["morning"],
            daily_total=2,
            diegetic_today=DIEGETIC_MAX_PER_DAY,
            time_since_last_initiative_sec=long_gap,
        ).reason
        == "diegetic_daily_cap"
    )
    assert (
        _decide(
            "proactivity",
            slot="afternoon",
            used_slots=["morning"],
            daily_total=2,
            proactive_today=PROACTIVE_MAX_PER_DAY,
            time_since_last_initiative_sec=long_gap,
        ).reason
        == "proactive_daily_cap"
    )
