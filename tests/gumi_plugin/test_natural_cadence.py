"""Tests for the flag-gated natural-cadence layer in cron_wiring.

Contract:
- everything is a seeded hash of subject|lane|date: deterministic, replayable;
- flag off (default) -> no skip, legacy jitter unchanged;
- checkin lane is never skipped (it carries the measurement instrument);
- diegetic gate message carries a deterministic `hook:` flag.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from relic.gumi_plugin.cron_wiring import (
    _DIEGETIC_HOOK_PCT,
    _NATURAL_SKIP_PCT,
    _diegetic_hook_today,
    _natural_cadence_enabled,
    _natural_cadence_skip_today,
    _seeded_roll,
    _window_jitter_minute,
)

NOW = datetime(2026, 6, 9, 15, 0, tzinfo=timezone.utc)


class TestFlag:
    def test_disabled_by_default(self, monkeypatch):
        monkeypatch.delenv("RELIC_NATURAL_CADENCE", raising=False)
        assert _natural_cadence_enabled() is False

    def test_enabled_by_env(self, monkeypatch):
        monkeypatch.setenv("RELIC_NATURAL_CADENCE", "1")
        assert _natural_cadence_enabled() is True


class TestSkipDays:
    def test_deterministic_per_day(self):
        a = _natural_cadence_skip_today("daniele", "diegetic", NOW)
        b = _natural_cadence_skip_today("daniele", "diegetic", NOW)
        assert a == b

    def test_checkin_never_skipped(self):
        for day in range(1, 29):
            now = datetime(2026, 6, day, 12, 0, tzinfo=timezone.utc)
            assert _natural_cadence_skip_today("daniele", "checkin", now) is False

    def test_skip_rate_matches_configured_pct(self):
        """Across many seeded days the empirical skip rate tracks the config."""
        days = [datetime(2026, m, d, 12, 0, tzinfo=timezone.utc)
                for m in range(1, 13) for d in range(1, 29)]
        for lane in ("diegetic", "proactivity"):
            skips = sum(_natural_cadence_skip_today("daniele", lane, d) for d in days)
            rate = 100.0 * skips / len(days)
            assert abs(rate - _NATURAL_SKIP_PCT[lane]) < 8.0, (lane, rate)

    def test_varies_across_subjects(self):
        days = [datetime(2026, 6, d, 12, 0, tzinfo=timezone.utc) for d in range(1, 29)]
        seq_a = [_natural_cadence_skip_today("daniele", "diegetic", d) for d in days]
        seq_b = [_natural_cadence_skip_today("barbara", "diegetic", d) for d in days]
        assert seq_a != seq_b


class TestDiegeticHook:
    def test_deterministic(self):
        assert _diegetic_hook_today("daniele", NOW) == _diegetic_hook_today("daniele", NOW)

    def test_hook_rate_matches_configured_pct(self):
        days = [datetime(2026, m, d, 12, 0, tzinfo=timezone.utc)
                for m in range(1, 13) for d in range(1, 29)]
        hooks = sum(_diegetic_hook_today("daniele", d) for d in days)
        rate = 100.0 * hooks / len(days)
        assert abs(rate - _DIEGETIC_HOOK_PCT) < 8.0, rate

    def test_seeded_roll_range(self):
        rolls = [_seeded_roll(f"x|{i}") for i in range(500)]
        assert all(0 <= r <= 99 for r in rolls)


class TestJitter:
    WINDOW = (9, 0, 11, 0)  # 120 min window

    def test_legacy_path_unchanged_when_flag_off(self, monkeypatch):
        monkeypatch.delenv("RELIC_NATURAL_CADENCE", raising=False)
        date = datetime(2026, 6, 9)
        m1 = _window_jitter_minute("daniele", self.WINDOW, date)
        m2 = _window_jitter_minute("daniele", self.WINDOW, date)
        assert m1 == m2

    def test_natural_jitter_deterministic_and_in_window(self, monkeypatch):
        monkeypatch.setenv("RELIC_NATURAL_CADENCE", "1")
        start = self.WINDOW[0] * 60 + self.WINDOW[1]
        end = self.WINDOW[2] * 60 + self.WINDOW[3]
        for day in range(1, 29):
            date = datetime(2026, 6, day)
            m1 = _window_jitter_minute("daniele", self.WINDOW, date)
            m2 = _window_jitter_minute("daniele", self.WINDOW, date)
            assert m1 == m2
            # Stays inside the window with the 30-min end reserve.
            assert start <= m1 <= end - 30

    def test_natural_jitter_varies_across_days(self, monkeypatch):
        monkeypatch.setenv("RELIC_NATURAL_CADENCE", "1")
        minutes = {
            _window_jitter_minute("daniele", self.WINDOW, datetime(2026, 6, day))
            for day in range(1, 29)
        }
        assert len(minutes) > 5, "fire minute should spread across the window day-to-day"


class TestDiegeticGateHookLine:
    def test_gate_message_carries_hook_flag(self, monkeypatch, tmp_path):
        """_evaluate_decision diegetic branch appends a deterministic hook line."""
        from relic.gumi_plugin import cron_wiring
        from relic.hermes_runtime import RuntimeDecision

        monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes"))
        monkeypatch.delenv("RELIC_NATURAL_CADENCE", raising=False)
        monkeypatch.setattr(cron_wiring, "_is_globally_paused", lambda: False)
        monkeypatch.setattr(cron_wiring, "_pro_checkin_allowed", lambda s: True)
        monkeypatch.setattr(cron_wiring, "_is_quiet_hours", lambda s: False)
        monkeypatch.setattr(cron_wiring, "_is_platform_not_allowlisted", lambda s: False)
        monkeypatch.setattr(cron_wiring, "_is_subject_paused", lambda s: False)
        monkeypatch.setattr(cron_wiring, "_is_continuity_scope_paused", lambda s: False)
        monkeypatch.setattr(cron_wiring, "_is_late_night_blocked", lambda s: False)
        monkeypatch.setattr(cron_wiring, "_select_media_type", lambda s, h, n: "text")

        decision, reasons, data = cron_wiring._evaluate_decision(
            "test_subj", "gumi-test", "profile-test", decision_type="diegetic"
        )
        assert decision == RuntimeDecision.CANDIDATE
        msg = data["message"]
        assert "\nhook: " in msg
        assert msg.splitlines()[-1] in ("hook: true", "hook: false")

    def test_natural_cadence_skip_returns_no_reply(self, monkeypatch, tmp_path):
        from relic.gumi_plugin import cron_wiring
        from relic.hermes_runtime import RuntimeDecision, RuntimeDecisionReason

        monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes"))
        monkeypatch.setenv("RELIC_NATURAL_CADENCE", "1")
        monkeypatch.setattr(cron_wiring, "_is_globally_paused", lambda: False)
        monkeypatch.setattr(cron_wiring, "_pro_checkin_allowed", lambda s: True)
        monkeypatch.setattr(cron_wiring, "_is_quiet_hours", lambda s: False)
        monkeypatch.setattr(cron_wiring, "_is_platform_not_allowlisted", lambda s: False)
        monkeypatch.setattr(cron_wiring, "_is_subject_paused", lambda s: False)
        monkeypatch.setattr(cron_wiring, "_is_continuity_scope_paused", lambda s: False)
        monkeypatch.setattr(cron_wiring, "_is_late_night_blocked", lambda s: False)
        monkeypatch.setattr(cron_wiring, "_natural_cadence_skip_today", lambda s, t, n: True)

        decision, reasons, data = cron_wiring._evaluate_decision(
            "test_subj", "gumi-test", "profile-test", decision_type="diegetic"
        )
        assert decision == RuntimeDecision.NO_REPLY
        assert RuntimeDecisionReason.natural_cadence_skip in reasons
        assert data is None
