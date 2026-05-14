"""Tests: EscalationNotifier — contacts loading, filtering, audit log, notify flow."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from relic.safety.escalation_notifier import (
    _load_escalation_contacts,
    _should_notify,
    notify_escalation,
)


class TestShouldNotify:
    def test_all_matches_everything(self) -> None:
        assert _should_notify({"notify_on": ["all"]}, "crisis_language") is True

    def test_specific_match(self) -> None:
        assert _should_notify({"notify_on": ["crisis_language"]}, "crisis_language") is True

    def test_specific_no_match(self) -> None:
        assert _should_notify({"notify_on": ["crisis_language"]}, "dependency_escalation") is False

    def test_empty_notify_on_no_match(self) -> None:
        assert _should_notify({"notify_on": []}, "crisis_language") is False


class TestLoadEscalationContacts:
    def test_loads_from_delivery_policy(self, tmp_path: Path) -> None:
        contacts = [{"name": "Dr. Rossi", "method": "email", "value": "rossi@uni.it", "notify_on": ["all"]}]
        policy_file = tmp_path / "delivery_policy.json"
        policy_file.write_text(json.dumps({"escalation_contacts": contacts}))

        mock_reg = MagicMock()
        mock_reg._delivery_policy_path.return_value = policy_file

        with patch("relic.profile.registry.ProfileRegistry", return_value=mock_reg):
            result = _load_escalation_contacts("s1")

        assert len(result) == 1
        assert result[0]["name"] == "Dr. Rossi"

    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        mock_reg = MagicMock()
        mock_reg._delivery_policy_path.return_value = tmp_path / "no.json"

        with patch("relic.profile.registry.ProfileRegistry", return_value=mock_reg):
            assert _load_escalation_contacts("s1") == []

    def test_no_contacts_key_returns_empty(self, tmp_path: Path) -> None:
        policy_file = tmp_path / "delivery_policy.json"
        policy_file.write_text(json.dumps({"timezone": "Europe/Rome"}))

        mock_reg = MagicMock()
        mock_reg._delivery_policy_path.return_value = policy_file

        with patch("relic.profile.registry.ProfileRegistry", return_value=mock_reg):
            assert _load_escalation_contacts("s1") == []


class TestNotifyEscalation:
    def test_writes_audit_log(self) -> None:
        contacts = [{"name": "Dr. Rossi", "method": "email", "value": "r@uni.it", "notify_on": ["all"]}]

        with patch("relic.safety.escalation_notifier._load_escalation_contacts", return_value=contacts):
            with patch("relic.safety.escalation_notifier._write_audit_log") as mock_log:
                with patch("relic.safety.escalation_notifier._send_email", return_value=False):
                    results = notify_escalation("s1", "crisis_language")

        mock_log.assert_called_once_with("s1", "crisis_language", "Dr. Rossi", "email")
        assert results[0]["delivered"] is False

    def test_no_contacts_returns_empty(self) -> None:
        with patch("relic.safety.escalation_notifier._load_escalation_contacts", return_value=[]):
            assert notify_escalation("s1", "crisis_language") == []

    def test_signal_filtered_by_notify_on(self) -> None:
        contacts = [{"name": "X", "method": "email", "value": "x@x.com", "notify_on": ["crisis_language"]}]

        with patch("relic.safety.escalation_notifier._load_escalation_contacts", return_value=contacts):
            with patch("relic.safety.escalation_notifier._write_audit_log") as mock_log:
                notify_escalation("s1", "dependency_escalation")

        mock_log.assert_not_called()

    def test_email_delivered_marked_true(self) -> None:
        contacts = [{"name": "X", "method": "email", "value": "x@x.com", "notify_on": ["all"]}]

        with patch("relic.safety.escalation_notifier._load_escalation_contacts", return_value=contacts):
            with patch("relic.safety.escalation_notifier._write_audit_log"):
                with patch("relic.safety.escalation_notifier._send_email", return_value=True):
                    results = notify_escalation("s1", "crisis_language")

        assert results[0]["delivered"] is True
