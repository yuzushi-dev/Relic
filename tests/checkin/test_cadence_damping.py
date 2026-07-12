"""Tests for cadence reconciliation + reach damping (Plan §Task 4)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from relic.checkin.features import (
    CadenceState,
    _apply_diegetic_disengagement,
    compute_reach_score,
    load_cadence_state,
    reconcile_cadence_outcome,
    save_cadence_state,
)


def test_unanswered_transition_increments_once():
    state = CadenceState(subject_id="s1")
    event = {
        "outcome_status_before": "delivered",
        "outcome_status": "unanswered_24h",
        "decision_type": "checkin",
    }
    new_state = reconcile_cadence_outcome(state, event)
    assert new_state.non_response_streak == 1
    assert new_state.followup_non_response_streak == 0


def test_silent_tick_does_not_increment():
    state = CadenceState(subject_id="s1", non_response_streak=2)
    event = {"outcome_status": "silent", "decision_type": "checkin"}
    new_state = reconcile_cadence_outcome(state, event)
    assert new_state.non_response_streak == 2


def test_boundary_sets_cap_without_reset():
    state = CadenceState(subject_id="s1", non_response_streak=3)
    new_state = reconcile_cadence_outcome(state, {"boundary_frequency_cap_per_day": 1})
    assert new_state.non_response_streak == 3
    assert new_state.frequency_cap_per_day == 1


def test_decay_requires_recent_subject_message():
    now = datetime.now(timezone.utc)
    state = CadenceState(
        subject_id="s1",
        non_response_streak=3,
        last_delivered_initiative_at=now - timedelta(days=8),
        last_subject_msg_at=now - timedelta(days=2),
    )
    new_state = reconcile_cadence_outcome(state, {"now": now})
    assert new_state.non_response_streak == 2


def test_decay_skips_when_subject_silent_too_long():
    now = datetime.now(timezone.utc)
    state = CadenceState(
        subject_id="s1",
        non_response_streak=3,
        last_delivered_initiative_at=now - timedelta(days=8),
        last_subject_msg_at=now - timedelta(days=14),
    )
    new_state = reconcile_cadence_outcome(state, {"now": now})
    assert new_state.non_response_streak == 3


def test_answered_resets_both_streaks():
    state = CadenceState(
        subject_id="s1",
        non_response_streak=2,
        followup_non_response_streak=1,
    )
    new_state = reconcile_cadence_outcome(state, {"outcome_status": "answered"})
    assert new_state.non_response_streak == 0
    assert new_state.followup_non_response_streak == 0
    assert new_state.last_reply_at is not None


def test_diegetic_frequency_relaxes_up_after_time_window():
    now = datetime.now(timezone.utc)
    state = CadenceState(
        subject_id="s1",
        diegetic_frequency=0.2,
        last_diegetic_relax_at=now - timedelta(days=2),
    )

    new_state = reconcile_cadence_outcome(state, {"now": now})

    assert new_state.diegetic_frequency is not None
    assert new_state.diegetic_frequency > 0.2
    assert new_state.last_diegetic_relax_at == now


def test_first_positive_diegetic_reply_initializes_and_raises_knobs():
    now = datetime.now(timezone.utc)
    state = CadenceState(subject_id="s1")

    new_state = reconcile_cadence_outcome(
        state,
        {
            "outcome_status": "answered",
            "decision_type": "diegetic",
            "reply_valence": 0.4,
            "now": now,
        },
    )

    assert new_state.diegetic_intensity == pytest.approx(0.35)
    assert new_state.diegetic_frequency == pytest.approx(0.6)
    assert new_state.last_diegetic_relax_at == now


def test_negative_diegetic_reply_lowers_intensity_and_frequency():
    now = datetime.now(timezone.utc)
    state = CadenceState(
        subject_id="s1",
        diegetic_intensity=0.6,
        diegetic_frequency=0.8,
    )

    new_state = reconcile_cadence_outcome(
        state,
        {
            "outcome_status": "answered",
            "decision_type": "diegetic",
            "reply_valence": -0.3,
            "now": now,
        },
    )

    assert new_state.diegetic_intensity == pytest.approx(0.4)
    assert new_state.diegetic_frequency == pytest.approx(0.48)
    assert new_state.last_diegetic_relax_at == now


def test_two_consecutive_ignored_diegetic_deliveries_halve_frequency():
    now = datetime.now(timezone.utc)
    state = CadenceState(
        subject_id="s1",
        diegetic_non_response_streak=1,
        diegetic_frequency=0.8,
    )

    new_state = reconcile_cadence_outcome(
        state,
        {
            "outcome_status_before": "delivered",
            "outcome_status": "unanswered_24h",
            "decision_type": "diegetic",
            "now": now,
        },
    )

    assert new_state.diegetic_non_response_streak == 2
    assert new_state.diegetic_frequency == pytest.approx(0.4)
    assert new_state.last_diegetic_relax_at == now


def test_diegetic_unanswered_increments_diegetic_streak_only_for_diegetic():
    state = CadenceState(subject_id="s1")

    checkin_state = reconcile_cadence_outcome(
        state,
        {
            "outcome_status_before": "delivered",
            "outcome_status": "unanswered_24h",
            "decision_type": "checkin",
        },
    )
    diegetic_state = reconcile_cadence_outcome(
        state,
        {
            "outcome_status_before": "delivered",
            "outcome_status": "unanswered_24h",
            "decision_type": "diegetic",
        },
    )

    assert checkin_state.diegetic_non_response_streak == 0
    assert diegetic_state.diegetic_non_response_streak == 1


def test_answered_resets_diegetic_streak_only_for_diegetic():
    state = CadenceState(
        subject_id="s1",
        non_response_streak=2,
        followup_non_response_streak=1,
        diegetic_non_response_streak=3,
    )

    checkin_state = reconcile_cadence_outcome(
        state,
        {"outcome_status": "answered", "decision_type": "checkin"},
    )
    diegetic_state = reconcile_cadence_outcome(
        state,
        {"outcome_status": "answered", "decision_type": "diegetic"},
    )

    assert checkin_state.non_response_streak == 0
    assert checkin_state.followup_non_response_streak == 0
    assert checkin_state.diegetic_non_response_streak == 3
    assert diegetic_state.non_response_streak == 0
    assert diegetic_state.followup_non_response_streak == 0
    assert diegetic_state.diegetic_non_response_streak == 0


def test_non_diegetic_events_do_not_touch_diegetic_knobs():
    now = datetime.now(timezone.utc)
    state = CadenceState(
        subject_id="s1",
        diegetic_intensity=0.55,
        diegetic_frequency=0.45,
        last_decay_at=now,
        # Block the (now decoupled) C2 relax so this test isolates what it's
        # meant to isolate: that a non-diegetic answered event does not
        # invoke _apply_diegetic_answered_reaction.
        last_diegetic_relax_at=now,
    )

    new_state = reconcile_cadence_outcome(
        state,
        {
            "outcome_status": "answered",
            "decision_type": "checkin",
            "reply_valence": -0.6,
            "now": now,
        },
    )

    assert new_state.diegetic_intensity == pytest.approx(0.55)
    assert new_state.diegetic_frequency == pytest.approx(0.45)


def test_followup_unanswered_increments_followup_streak():
    state = CadenceState(subject_id="s1")
    event = {
        "outcome_status_before": "delivered",
        "outcome_status": "unanswered_24h",
        "decision_type": "followup",
    }
    new_state = reconcile_cadence_outcome(state, event)
    assert new_state.non_response_streak == 1
    assert new_state.followup_non_response_streak == 1
    assert new_state.diegetic_non_response_streak == 0


def test_followup_multiplier_reduces_reach_score_more_aggressively():
    assert compute_reach_score(1, 2) < 0.7


def test_compute_reach_score_matches_spec():
    assert compute_reach_score(0, 0) == pytest.approx(1.0)
    assert compute_reach_score(1, 0) == pytest.approx(0.7)
    assert compute_reach_score(3, 0) == pytest.approx(0.7 ** 3)
    assert compute_reach_score(1, 1) == pytest.approx(0.7 ** 3)


def test_unanswered_without_outcome_status_before_does_not_increment():
    """Reviewer fix: sparse historical rows with outcome_status_before=None
    must NOT bump the streak on replay."""
    from relic.checkin.features import CadenceState, reconcile_cadence_outcome

    state = CadenceState(subject_id="s1", non_response_streak=0)
    new_state = reconcile_cadence_outcome(
        state,
        {"outcome_status": "unanswered_24h", "decision_type": "checkin"},
    )
    assert new_state.non_response_streak == 0


def test_diegetic_relax_fires_even_when_last_decay_at_is_fresh():
    """Regression for the C2 deadlock (bug 1): the checkin-lane streak decay
    stamps last_decay_at almost every day, which used to gate the diegetic
    relax and starve it below the naturalness-policy threshold (0.25). The
    relax now runs off its own dedicated timestamp, so a fresh last_decay_at
    no longer blocks it."""
    now = datetime.now(timezone.utc)
    state = CadenceState(
        subject_id="s1",
        diegetic_frequency=0.2175,
        last_decay_at=now,  # fresh - would have blocked the old (buggy) gate
        last_diegetic_relax_at=None,  # never relaxed -> fires immediately
    )

    new_state = reconcile_cadence_outcome(state, {"now": now})

    assert new_state.diegetic_frequency == pytest.approx(0.3175)
    assert new_state.last_diegetic_relax_at == now
    assert new_state.last_decay_at == now  # untouched by the relax path


def test_diegetic_relax_does_not_fire_within_a_day():
    now = datetime.now(timezone.utc)
    state = CadenceState(
        subject_id="s1",
        diegetic_frequency=0.2175,
        last_diegetic_relax_at=now - timedelta(hours=12),
    )

    new_state = reconcile_cadence_outcome(state, {"now": now})

    assert new_state.diegetic_frequency == pytest.approx(0.2175)
    assert new_state.last_diegetic_relax_at == now - timedelta(hours=12)


def test_diegetic_disengagement_stamps_relax_timestamp_not_decay():
    now = datetime.now(timezone.utc)
    state = CadenceState(subject_id="s1", diegetic_frequency=0.8)

    new_state = _apply_diegetic_disengagement(state, now)

    assert new_state.last_diegetic_relax_at == now
    assert new_state.last_decay_at is None


def test_save_cadence_state_migrates_legacy_schema_missing_relax_column():
    """save_cadence_state must ALTER TABLE in an opportunistic, fail-soft way
    when writing to a per-subject DB created before last_diegetic_relax_at
    existed, then load_cadence_state must read the migrated value back."""
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute(
            """CREATE TABLE checkin_cadence_state (
                subject_id                    TEXT PRIMARY KEY,
                non_response_streak           INTEGER NOT NULL DEFAULT 0,
                followup_non_response_streak  INTEGER NOT NULL DEFAULT 0,
                diegetic_non_response_streak  INTEGER,
                last_delivered_initiative_at  TEXT,
                last_diegetic_delivered_at    TEXT,
                last_unanswered_delivery_at   TEXT,
                last_reply_at                 TEXT,
                last_subject_msg_at           TEXT,
                last_boundary_at              TEXT,
                last_decay_at                 TEXT,
                frequency_cap_per_day         INTEGER,
                diegetic_intensity            REAL,
                diegetic_frequency            REAL,
                updated_at                    TEXT NOT NULL
            )"""
        )
        conn.commit()

        now = datetime.now(timezone.utc)
        state = CadenceState(subject_id="s1", last_diegetic_relax_at=now, updated_at=now)
        save_cadence_state(conn, state)
        conn.commit()

        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(checkin_cadence_state)").fetchall()
        }
        assert "last_diegetic_relax_at" in columns

        reloaded = load_cadence_state(conn, "s1")
        assert reloaded.last_diegetic_relax_at == now
    finally:
        conn.close()


def test_sparse_replay_without_reply_valence_uses_safe_default_for_diegetic_answer():
    now = datetime.now(timezone.utc)
    state = CadenceState(subject_id="s1")

    new_state = reconcile_cadence_outcome(
        state,
        {
            "outcome_status": "answered",
            "decision_type": "diegetic",
            "now": now,
        },
    )

    assert new_state.diegetic_intensity == pytest.approx(0.35)
    assert new_state.diegetic_frequency == pytest.approx(0.6)
