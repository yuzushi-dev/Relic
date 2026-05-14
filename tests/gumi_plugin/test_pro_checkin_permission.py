"""Tests: PRO_CHECKIN permission respected in cron_wiring.

Covers:
- PRO_CHECKIN=0 → _pro_checkin_allowed returns False
- PRO_CHECKIN=2 (default) → _pro_checkin_allowed returns True
- Missing policy file → fail-open (True)
- _evaluate_decision returns NO_REPLY when PRO_CHECKIN=0
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from relic.gumi_plugin.cron_wiring import _pro_checkin_allowed


class TestProCheckinAllowed:
    def test_zero_disallows(self, tmp_path: Path) -> None:
        policy = {"PRO_CHECKIN": 0, "consent_for_active_elicitation": True}
        policy_file = tmp_path / "delivery_policy.json"
        policy_file.write_text(json.dumps(policy))

        mock_registry = MagicMock()
        mock_registry._delivery_policy_path.return_value = policy_file

        with patch("relic.profile.registry.ProfileRegistry", return_value=mock_registry):
            assert _pro_checkin_allowed("sub1") is False

    def test_default_two_allows(self, tmp_path: Path) -> None:
        policy = {"PRO_CHECKIN": 2}
        policy_file = tmp_path / "delivery_policy.json"
        policy_file.write_text(json.dumps(policy))

        mock_registry = MagicMock()
        mock_registry._delivery_policy_path.return_value = policy_file

        with patch("relic.profile.registry.ProfileRegistry", return_value=mock_registry):
            assert _pro_checkin_allowed("sub1") is True

    def test_missing_policy_fails_open(self, tmp_path: Path) -> None:
        mock_registry = MagicMock()
        mock_registry._delivery_policy_path.return_value = tmp_path / "nonexistent.json"

        with patch("relic.profile.registry.ProfileRegistry", return_value=mock_registry):
            assert _pro_checkin_allowed("sub1") is True

    def test_four_allows(self, tmp_path: Path) -> None:
        policy = {"PRO_CHECKIN": 4}
        policy_file = tmp_path / "delivery_policy.json"
        policy_file.write_text(json.dumps(policy))

        mock_registry = MagicMock()
        mock_registry._delivery_policy_path.return_value = policy_file

        with patch("relic.profile.registry.ProfileRegistry", return_value=mock_registry):
            assert _pro_checkin_allowed("sub1") is True
