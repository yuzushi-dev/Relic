"""Tests that _evaluate_decision() respects the PauseController gate.

Contract:
- _is_globally_paused() returns False when PauseController.is_any_session_paused() is False
- _is_globally_paused() returns True when PauseController.is_any_session_paused() is True
- _is_globally_paused() returns False (fail-open) when PauseController raises
- _is_globally_paused() logs ERROR (not silently swallows) on exception
- make_decision() returns NO_REPLY when globally paused
- make_decision() does not call PauseController when force=True (bypass)
"""
from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

from relic.gumi_plugin.cron_wiring import _is_globally_paused
from relic.hermes_runtime import RuntimeDecision


class TestIsGloballyPaused:
    def test_returns_false_when_not_paused(self):
        with patch("relic.control.pause.PauseController.is_any_session_paused", return_value=False):
            assert _is_globally_paused() is False

    def test_returns_true_when_paused(self):
        with patch("relic.control.pause.PauseController.is_any_session_paused", return_value=True):
            assert _is_globally_paused() is True

    def test_fail_open_on_import_error(self):
        with patch("relic.control.pause.PauseController.__init__", side_effect=ImportError("no module")):
            assert _is_globally_paused() is False

    def test_fail_open_on_pause_controller_exception(self):
        with patch("relic.control.pause.PauseController.is_any_session_paused", side_effect=RuntimeError("db error")):
            assert _is_globally_paused() is False

    def test_logs_error_on_exception(self, caplog):
        with caplog.at_level(logging.ERROR, logger="relic.gumi_plugin.cron_wiring"):
            with patch("relic.control.pause.PauseController.is_any_session_paused", side_effect=RuntimeError("disk full")):
                result = _is_globally_paused()
        assert result is False
        assert any("disk full" in r.message for r in caplog.records)


class TestMakeDecisionPauseGate:
    def test_globally_paused_returns_no_reply(self):
        with patch("relic.gumi_plugin.cron_wiring._is_globally_paused", return_value=True):
            from relic.gumi_plugin.cron_wiring import make_decision

            decision, reasons, data = make_decision(
                subject_id="test_subj",
                gumi_instance_id="",
                hermes_profile_id="",
            )
        assert decision == RuntimeDecision.NO_REPLY

    def test_not_paused_proceeds_to_normal_evaluation(self):
        """When not paused, make_decision proceeds past the pause gate."""
        with (
            patch("relic.gumi_plugin.cron_wiring._is_globally_paused", return_value=False),
            patch("relic.gumi_plugin.cron_wiring._pro_checkin_allowed", return_value=False),
        ):
            from relic.gumi_plugin.cron_wiring import make_decision

            decision, reasons, data = make_decision(
                subject_id="test_subj",
                gumi_instance_id="",
                hermes_profile_id="",
            )
        # PRO_CHECKIN disabled → NO_REPLY but via different path (pause gate passed)
        assert decision == RuntimeDecision.NO_REPLY

    def test_force_bypasses_pause_gate(self):
        """force=True delivers directly without checking pause state."""
        with (
            patch("relic.gumi_plugin.cron_wiring._is_globally_paused", return_value=True),
            patch("relic.gumi_plugin.cron_wiring._select_media_type", return_value="text"),
            patch("relic.gumi_plugin.cron_wiring._subject_now") as mock_now,
        ):
            from datetime import datetime, timezone
            mock_now.return_value = datetime.now(timezone.utc)
            from relic.gumi_plugin.cron_wiring import make_decision

            decision, _, _ = make_decision(
                subject_id="test_subj",
                gumi_instance_id="",
                hermes_profile_id="",
                force=True,
            )
        assert decision == RuntimeDecision.DELIVER
