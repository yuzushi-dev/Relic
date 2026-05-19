"""Tests for cadence reconciliation + reach damping (Plan §Task 4)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from relic.checkin.features import (
    CadenceState,
    compute_reach_score,
    reconcile_cadence_outcome,
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


def test_followup_multiplier_reduces_reach_score_more_aggressively():
    assert compute_reach_score(1, 2) < 0.7


def test_compute_reach_score_matches_spec():
    assert compute_reach_score(0, 0) == pytest.approx(1.0)
    assert compute_reach_score(1, 0) == pytest.approx(0.7)
    assert compute_reach_score(3, 0) == pytest.approx(0.7 ** 3)
    assert compute_reach_score(1, 1) == pytest.approx(0.7 ** 3)
