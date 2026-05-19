"""Tests: EscalationNotifier — contacts loading, filtering, audit log, notify flow."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from relic.safety.escalation_notifier import (
    _load_escalation_contacts,
    _send_email,
    _send_telegram_message,
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

    def test_loads_from_baseline_when_delivery_policy_missing(self, tmp_path: Path) -> None:
        contacts = [
            {"name": "Dr. Rossi", "method": "email", "value": "rossi@uni.it", "notify_on": ["all"]},
            {"name": "Dr. Rossi", "method": "telegram", "value": "123456789", "notify_on": ["all"]},
        ]
        baseline_file = tmp_path / "baseline_user_profile.json"
        baseline_file.write_text(json.dumps({"escalation_contacts": contacts}))

        mock_reg = MagicMock()
        mock_reg._delivery_policy_path.return_value = tmp_path / "delivery_policy.json"

        with patch("relic.profile.registry.ProfileRegistry", return_value=mock_reg):
            result = _load_escalation_contacts("s1")

        assert result == contacts

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

    def test_email_and_telegram_contacts_are_both_attempted(self) -> None:
        contacts = [
            {"name": "X", "method": "email", "value": "x@x.com", "notify_on": ["all"]},
            {"name": "X", "method": "telegram", "value": "123456789", "notify_on": ["all"]},
        ]

        with patch("relic.safety.escalation_notifier._load_escalation_contacts", return_value=contacts):
            with patch("relic.safety.escalation_notifier._write_audit_log"):
                with patch("relic.safety.escalation_notifier._send_email", return_value=True) as email:
                    with patch(
                        "relic.safety.escalation_notifier._send_telegram_message",
                        return_value=True,
                    ) as telegram:
                        results = notify_escalation(
                            "s1",
                            "crisis_language",
                            evidence_refs=["turn-abc123"],
                            warning_tier="T4_crisis",
                            confidence=0.85,
                        )

        email.assert_called_once()
        telegram.assert_called_once_with(
            "123456789",
            "s1",
            "crisis_language",
            evidence_refs=["turn-abc123"],
            warning_tier="T4_crisis",
            confidence=0.85,
        )
        assert [result["method"] for result in results] == ["email", "telegram"]
        assert all(result["delivered"] is True for result in results)

    def test_email_receives_redacted_review_metadata(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "RELIC_SMTP_HOST": "smtp.test",
                "RELIC_SMTP_USER": "sender@test",
                "RELIC_SMTP_PASS": "pw",
            },
        ):
            with patch("smtplib.SMTP") as smtp_cls:
                assert _send_email(
                    "reviewer@test",
                    "s1",
                    "crisis_language",
                    evidence_refs=["turn-abc123"],
                    warning_tier="T4_crisis",
                    confidence=0.85,
                ) is True

        message = smtp_cls.return_value.__enter__.return_value.send_message.call_args.args[0]
        body = message.get_content()
        assert "Evidence refs: turn-abc123" in body
        assert "Warning tier: T4_crisis" in body
        assert "Confidence: 0.85" in body

    def test_send_telegram_message_posts_redacted_metadata(self) -> None:
        with patch.dict("os.environ", {"RELIC_TELEGRAM_BOT_TOKEN": "123:test-token"}):
            with patch("urllib.request.urlopen") as urlopen:
                urlopen.return_value.__enter__.return_value.read.return_value = b'{"ok": true}'

                assert _send_telegram_message(
                    "telegram:123456789",
                    "s1",
                    "crisis_language",
                    evidence_refs=["turn-abc123"],
                    warning_tier="T4_crisis",
                    confidence=0.85,
                ) is True

        request = urlopen.call_args.args[0]
        body = request.data.decode("utf-8")
        assert "chat_id=123456789" in body
        assert "turn-abc123" in body
        assert "T4_crisis" in body
        assert "crisis_language" in body
        assert "raw" not in body.lower()
