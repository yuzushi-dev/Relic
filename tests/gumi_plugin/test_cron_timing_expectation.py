"""Tests: response_timing_expectation shifts delivery window target minute."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from relic.gumi_plugin.cron_wiring import _response_timing_factor, _window_jitter_minute


WINDOW = (9, 0, 11, 0)  # 9:00-11:00 → 120 min span, 90 min available after -30 reserve
DATE = datetime(2025, 1, 15)


class TestResponseTimingFactor:
    def _make_profile(self, tmp_path: Path, value: str) -> MagicMock:
        baseline = {"interaction_preferences": {"response_timing_expectation": value}}
        (tmp_path / "baseline_user_profile.json").write_text(json.dumps(baseline))
        mock_profile = MagicMock()
        mock_profile.relic_subject_home = tmp_path
        return mock_profile

    def _patch_registry(self, mock_profile: MagicMock):
        mock_reg = MagicMock()
        mock_reg.get_subject.return_value = mock_profile
        return patch("relic.profile.registry.ProfileRegistry", return_value=mock_reg)

    def test_high_returns_low_factor(self, tmp_path: Path) -> None:
        profile = self._make_profile(tmp_path, "high")
        with self._patch_registry(profile):
            factor = _response_timing_factor("s1")
        assert factor == 0.25

    def test_medium_returns_midpoint(self, tmp_path: Path) -> None:
        profile = self._make_profile(tmp_path, "medium")
        with self._patch_registry(profile):
            factor = _response_timing_factor("s1")
        assert factor == 0.5

    def test_low_returns_high_factor(self, tmp_path: Path) -> None:
        profile = self._make_profile(tmp_path, "low")
        with self._patch_registry(profile):
            factor = _response_timing_factor("s1")
        assert factor == 0.85

    def test_missing_profile_fails_open(self, tmp_path: Path) -> None:
        mock_reg = MagicMock()
        mock_reg.get_subject.return_value = None
        with patch("relic.profile.registry.ProfileRegistry", return_value=mock_reg):
            assert _response_timing_factor("s1") == 0.5

    def test_unknown_value_falls_back_to_default(self, tmp_path: Path) -> None:
        profile = self._make_profile(tmp_path, "never_heard_of_this")
        with self._patch_registry(profile):
            factor = _response_timing_factor("s1")
        assert factor == 0.5


class TestWindowJitterMinuteTimingShift:
    """High-expectation subjects fire earlier than low-expectation in same window."""

    def _patch_factor(self, value: float):
        return patch("relic.gumi_plugin.cron_wiring._response_timing_factor", return_value=value)

    def test_high_expectation_fires_earlier_than_low(self) -> None:
        with self._patch_factor(0.25):
            early = _window_jitter_minute("s1", WINDOW, DATE)
        with self._patch_factor(0.85):
            late = _window_jitter_minute("s1", WINDOW, DATE)
        assert early <= late, f"high expectation should fire ≤ late: {early} vs {late}"

    def test_result_within_window(self) -> None:
        sh, sm, eh, em = WINDOW
        start = sh * 60 + sm
        end = eh * 60 + em
        with self._patch_factor(0.5):
            result = _window_jitter_minute("s1", WINDOW, DATE)
        assert start <= result < end, f"result {result} outside window [{start},{end})"
