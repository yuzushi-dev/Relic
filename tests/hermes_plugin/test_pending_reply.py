"""Tests for relic.hermes_plugin.pending_reply."""

from __future__ import annotations

import json

import pytest

from relic.hermes_plugin import pending_reply as pr


def test_is_capacity_error_positive():
    assert pr.is_capacity_error("API call failed after 3 retries: HTTP 429 - ...")
    assert pr.is_capacity_error("you have reached your weekly usage limit")
    assert pr.is_capacity_error("Rate limited. Waiting 2.2s")
    assert pr.is_capacity_error("429 Too Many Requests")


def test_is_capacity_error_negative():
    assert not pr.is_capacity_error("")
    assert not pr.is_capacity_error(None)  # type: ignore[arg-type]
    assert not pr.is_capacity_error("the model produced an empty response")
    assert not pr.is_capacity_error("invalid api key (401)")


def test_record_read_clear_roundtrip(tmp_path):
    assert pr.read_pending_reply(tmp_path) is None
    pr.record_pending_reply(tmp_path, now=1000.0)
    assert pr.read_pending_reply(tmp_path) == 1000.0
    # marker lives under state/
    assert (tmp_path / "state" / "pending_reply.json").exists()
    pr.clear_pending_reply(tmp_path)
    assert pr.read_pending_reply(tmp_path) is None


def test_record_keeps_earliest_timestamp(tmp_path):
    pr.record_pending_reply(tmp_path, now=1000.0)
    pr.record_pending_reply(tmp_path, now=5000.0)  # later failure must not overwrite
    assert pr.read_pending_reply(tmp_path) == 1000.0


def test_clear_is_idempotent(tmp_path):
    pr.clear_pending_reply(tmp_path)  # nothing to clear -> no raise
    pr.record_pending_reply(tmp_path, now=1.0)
    pr.clear_pending_reply(tmp_path)
    pr.clear_pending_reply(tmp_path)
    assert pr.read_pending_reply(tmp_path) is None


def test_ack_instruction_none_when_not_pending(tmp_path):
    assert pr.pending_ack_instruction(tmp_path, now=10_000.0) is None


def test_ack_instruction_none_under_or_at_threshold(tmp_path):
    pr.record_pending_reply(tmp_path, now=0.0)
    # 59 min -> no ack
    assert pr.pending_ack_instruction(tmp_path, now=59 * 60) is None
    # exactly 60 min -> still no ack (must strictly exceed)
    assert pr.pending_ack_instruction(tmp_path, now=3600) is None


def test_ack_instruction_present_over_threshold(tmp_path):
    pr.record_pending_reply(tmp_path, now=0.0)
    msg = pr.pending_ack_instruction(tmp_path, now=3600 + 60)  # 61 min
    assert msg is not None
    # instruction, not a hardcoded reply, and leaks no technical jargon
    assert "ritardo" in msg.lower()
    assert "429" not in msg
    assert "rate limit" not in msg.lower()


def test_ack_instruction_hours_wording(tmp_path):
    pr.record_pending_reply(tmp_path, now=0.0)
    msg = pr.pending_ack_instruction(tmp_path, now=3 * 3600)  # 3 hours
    assert msg is not None
    assert "ore" in msg


def test_read_handles_corrupt_marker(tmp_path):
    (tmp_path / "state").mkdir()
    (tmp_path / "state" / "pending_reply.json").write_text("{not json", encoding="utf-8")
    assert pr.read_pending_reply(tmp_path) is None
