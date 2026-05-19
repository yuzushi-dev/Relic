"""Tests for tools/replay_decisions.py (Plan §Task 10)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.replay_decisions import replay_event, run_replay


def _write(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def test_replay_produces_byte_stable_output(tmp_path: Path):
    src = tmp_path / "events.jsonl"
    _write(
        src,
        [
            {
                "event_id": "e1",
                "created_at": "2026-05-19T00:00:00+00:00",
                "decision_type": "checkin",
                "event_kind": "checkin",
                "posture": "observe",
                "features_json": {
                    "reach_score": 1.0,
                    "time_since_last_subject_msg_sec": 3600,
                },
            },
            {
                "event_id": "e2",
                "created_at": "2026-05-19T00:30:00+00:00",
                "decision_type": "proactivity",
                "event_kind": "silent",
                "posture": "quiet",
                "features_json": {
                    "reach_score": 1.0,
                    "salience_top": 0.8,
                    "time_since_last_subject_msg_sec": 7200,
                },
            },
        ],
    )

    out1 = tmp_path / "out1.jsonl"
    out2 = tmp_path / "out2.jsonl"
    run_replay(input_path=src, output_path=out1)
    run_replay(input_path=src, output_path=out2)
    assert out1.read_text() == out2.read_text()


def test_replay_emits_changed_flag_for_promoted_decision():
    record = replay_event(
        {
            "event_id": "e1",
            "decision_type": "proactivity",
            "event_kind": "silent",
            "posture": "quiet",
            "features_json": {
                "reach_score": 1.0,
                "salience_top": 0.8,
                "time_since_last_subject_msg_sec": 7200,
            },
        }
    )
    assert record["new_event_kind"] == "proactive"
    assert record["new_posture"] == "brief_share"
    assert record["changed"] is True


def test_replay_preserves_event_kind_when_unchanged():
    record = replay_event(
        {
            "event_id": "e3",
            "decision_type": "checkin",
            "event_kind": "checkin",
            "posture": "observe",
            "features_json": {
                "reach_score": 1.0,
                "time_since_last_subject_msg_sec": 3600,
            },
        }
    )
    assert record["new_event_kind"] == "checkin"
    assert record["new_posture"] == "observe"
    assert record["changed"] is False
