"""Tests for relic.checkin.metrics (Plan §Task 11)."""

from __future__ import annotations

import pytest

from relic.checkin.metrics import (
    message_jaccard,
    posture_entropy,
    rolling_repetition_rate,
    silent_rate,
    wake_agent_consistency,
)


def test_jaccard_identical_messages_is_one():
    assert message_jaccard("ciao tutto bene", "ciao tutto bene") == pytest.approx(1.0)


def test_jaccard_disjoint_messages_is_zero():
    assert message_jaccard("ciao tutto bene", "altrove altre cose") == pytest.approx(0.0)


def test_rolling_repetition_rate_threshold():
    msgs = [
        "ciao buongiorno",
        "ciao buonasera",
        "tutta altra storia",
    ]
    # first pair: jaccard 1/3 < 0.4 → 0 hit
    # second pair: jaccard 0 < 0.4 → 0 hit
    assert rolling_repetition_rate(msgs) == pytest.approx(0.0)


def test_rolling_repetition_rate_detects_repeat():
    msgs = [
        "ciao tutto bene amore",
        "ciao tutto bene amore",
        "completamente diverso",
    ]
    assert rolling_repetition_rate(msgs) == pytest.approx(0.5)


def test_posture_entropy_zero_for_monoculture():
    assert posture_entropy(["observe"] * 10) == pytest.approx(0.0)


def test_posture_entropy_above_one_bit_for_two_balanced_postures():
    postures = ["observe", "ask"] * 5
    assert posture_entropy(postures) == pytest.approx(1.0)


def test_silent_rate_within_band():
    events = [
        {"event_kind": "silent"},
        {"event_kind": "checkin"},
        {"event_kind": "silent"},
        {"event_kind": "followup"},
    ]
    assert silent_rate(events) == pytest.approx(0.5)


def test_wake_agent_consistency_perfect():
    events = [
        {"event_kind": "silent", "wake_agent_emitted": False},
        {"event_kind": "checkin", "wake_agent_emitted": True},
        {"event_kind": "followup", "wake_agent_emitted": True},
    ]
    assert wake_agent_consistency(events) == pytest.approx(1.0)


def test_wake_agent_consistency_flags_inversion():
    events = [
        {"event_kind": "silent", "wake_agent_emitted": True},
        {"event_kind": "checkin", "wake_agent_emitted": True},
    ]
    assert wake_agent_consistency(events) == pytest.approx(0.5)


def test_silent_rate_empty_returns_zero():
    assert silent_rate([]) == 0.0


def test_wake_agent_consistency_skips_when_field_missing():
    events = [
        {"event_kind": "silent"},
        {"event_kind": "checkin"},
    ]
    assert wake_agent_consistency(events) == pytest.approx(1.0)
