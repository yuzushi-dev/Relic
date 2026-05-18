"""Tests for _select_ask_decision and ask flag in DELIVER payload."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from relic.gumi_plugin import cron_wiring


def _init_relic_db(relic_home: Path, subject_id: str = "test_subj") -> Path:
    from relic.checkin.db_init import init_db, seed_facets
    sub = relic_home / "subjects" / subject_id
    sub.mkdir(parents=True)
    db_path = sub / "relic.db"
    conn = init_db(db_path)
    seed_facets(conn)
    conn.close()
    return db_path


def _force_ask_now(question_hint: str = "Velocità nel prendere decisioni"):
    return patch(
        "relic.gumi_plugin.cron_wiring.select_facet",
        create=True,
        return_value={
            "status": "ask_now",
            "selected_facet": "cognitive.decision_speed",
            "question_hint": question_hint,
        },
    )


class TestSelectAskDecision:
    def test_no_db_returns_false(self, tmp_path: Path):
        ask, hint = cron_wiring._select_ask_decision(
            "missing_subj",
            datetime(2026, 5, 18, 10, 0, tzinfo=timezone.utc),
            relic_home=tmp_path / "relic",
        )
        assert ask is False
        assert hint is None

    def test_returns_true_when_all_gates_pass(self, tmp_path: Path):
        relic_home = tmp_path / "relic"
        _init_relic_db(relic_home, "test_subj")
        # Find a date whose hash roll lands < 35
        base = datetime(2026, 5, 18, 10, 0, tzinfo=timezone.utc)
        for offset in range(0, 30):
            now = base + timedelta(days=offset)
            with patch(
                "relic.checkin.question_engine.select_facet",
                return_value={
                    "status": "ask_now",
                    "selected_facet": "cognitive.decision_speed",
                    "question_hint": "Spunto domanda",
                },
            ):
                ask, hint = cron_wiring._select_ask_decision(
                    "test_subj", now, relic_home=relic_home
                )
            if ask:
                assert hint == "Spunto domanda"
                return
        pytest.fail("no date roll under 35% in 30-day window — unexpected")

    def test_returns_false_when_select_facet_not_ask_now(self, tmp_path: Path):
        relic_home = tmp_path / "relic"
        _init_relic_db(relic_home, "test_subj")
        # Find a date whose roll passes (< 35)
        base = datetime(2026, 5, 18, 10, 0, tzinfo=timezone.utc)
        for offset in range(0, 30):
            now = base + timedelta(days=offset)
            with patch(
                "relic.checkin.question_engine.select_facet",
                return_value={"status": "no_candidate"},
            ):
                ask, hint = cron_wiring._select_ask_decision(
                    "test_subj", now, relic_home=relic_home
                )
            # Either gate blocked it or ask_now check failed — both fine
            assert ask is False
            assert hint is None

    def test_cooldown_blocks_recent_ask(self, tmp_path: Path):
        relic_home = tmp_path / "relic"
        db_path = _init_relic_db(relic_home, "test_subj")

        # Find a date whose daily roll would otherwise PASS (< 35) so we know
        # cooldown is the gate that blocks, not the probability roll.
        base = datetime(2026, 5, 18, 10, 0, tzinfo=timezone.utc)
        passing_now = None
        for offset in range(0, 30):
            candidate = base + timedelta(days=offset)
            with patch(
                "relic.checkin.question_engine.select_facet",
                return_value={
                    "status": "ask_now",
                    "selected_facet": "x",
                    "question_hint": "x",
                },
            ):
                ask, _ = cron_wiring._select_ask_decision(
                    "test_subj", candidate, relic_home=relic_home
                )
            if ask:
                passing_now = candidate
                break
        assert passing_now is not None, "could not find a passing date"

        # Inject an ask 1h before passing_now → cooldown must block.
        recent = (passing_now - timedelta(hours=1)).isoformat()
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "INSERT INTO checkin_exchanges (facet_id, question_text, asked_at) VALUES (?, ?, ?)",
            ("cognitive.decision_speed", "Domanda precedente", recent),
        )
        conn.commit()
        conn.close()

        with patch(
            "relic.checkin.question_engine.select_facet",
            return_value={
                "status": "ask_now",
                "selected_facet": "x",
                "question_hint": "x",
            },
        ):
            ask, _ = cron_wiring._select_ask_decision(
                "test_subj", passing_now, relic_home=relic_home
            )
        assert ask is False


class TestDeliverPayloadAskFlag:
    def test_ask_lines_appended_when_decision_true(self):
        with patch(
            "relic.gumi_plugin.cron_wiring._select_ask_decision",
            return_value=(True, "Velocità nel decidere"),
        ), patch(
            "relic.gumi_plugin.cron_wiring._select_media_type",
            return_value="text",
        ), patch(
            "relic.gumi_plugin.cron_wiring._is_globally_paused",
            return_value=False,
        ), patch(
            "relic.gumi_plugin.cron_wiring._pro_checkin_allowed",
            return_value=True,
        ), patch(
            "relic.gumi_plugin.cron_wiring._is_quiet_hours",
            return_value=False,
        ), patch(
            "relic.gumi_plugin.cron_wiring._is_platform_not_allowlisted",
            return_value=False,
        ), patch(
            "relic.gumi_plugin.cron_wiring._is_subject_paused",
            return_value=False,
        ), patch(
            "relic.gumi_plugin.cron_wiring._is_continuity_scope_paused",
            return_value=False,
        ), patch(
            "relic.gumi_plugin.cron_wiring._is_delivery_window_open",
            return_value=True,
        ), patch(
            "relic.gumi_plugin.cron_wiring.get_continuity_service"
        ) as svc_mock:
            svc_mock.return_value.due_followups.return_value = []
            decision, _reasons, data = cron_wiring._evaluate_decision(
                "subj", "gumi", "hermes"
            )
        assert data is not None
        msg = data["message"]
        assert msg.startswith("DELIVER")
        assert "tipo: text" in msg
        assert "ask: true" in msg
        assert "ask_topic: Velocità nel decidere" in msg

    def test_no_ask_lines_when_decision_false(self):
        with patch(
            "relic.gumi_plugin.cron_wiring._select_ask_decision",
            return_value=(False, None),
        ), patch(
            "relic.gumi_plugin.cron_wiring._select_media_type",
            return_value="text",
        ), patch(
            "relic.gumi_plugin.cron_wiring._is_globally_paused",
            return_value=False,
        ), patch(
            "relic.gumi_plugin.cron_wiring._pro_checkin_allowed",
            return_value=True,
        ), patch(
            "relic.gumi_plugin.cron_wiring._is_quiet_hours",
            return_value=False,
        ), patch(
            "relic.gumi_plugin.cron_wiring._is_platform_not_allowlisted",
            return_value=False,
        ), patch(
            "relic.gumi_plugin.cron_wiring._is_subject_paused",
            return_value=False,
        ), patch(
            "relic.gumi_plugin.cron_wiring._is_continuity_scope_paused",
            return_value=False,
        ), patch(
            "relic.gumi_plugin.cron_wiring._is_delivery_window_open",
            return_value=True,
        ), patch(
            "relic.gumi_plugin.cron_wiring.get_continuity_service"
        ) as svc_mock:
            svc_mock.return_value.due_followups.return_value = []
            decision, _reasons, data = cron_wiring._evaluate_decision(
                "subj", "gumi", "hermes"
            )
        assert data is not None
        assert "ask:" not in data["message"]
        assert "ask_topic:" not in data["message"]
