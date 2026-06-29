"""Tests for escalation contact collection in the bootstrap TUI."""
from __future__ import annotations

from io import StringIO
from pathlib import Path

from relic.profile._bootstrap_steps.boundaries import _collect_escalation_contacts
from relic.profile.registry import ProfileRegistry


def test_collect_escalation_contact_records_email_and_telegram() -> None:
    io_in = StringIO(
        "\n".join(
            [
                "y",
                "Dr. Rossi",
                "rossi@uni.it",
                "123456789",
                "crisis_language,self_harm_language",
                "n",
            ]
        )
        + "\n"
    )
    io_out = StringIO()

    contacts = _collect_escalation_contacts(io_in, io_out)

    assert contacts == [
        {
            "name": "Dr. Rossi",
            "method": "email",
            "value": "rossi@uni.it",
            "notify_on": ["crisis_language", "self_harm_language"],
        },
        {
            "name": "Dr. Rossi",
            "method": "telegram",
            "value": "123456789",
            "notify_on": ["crisis_language", "self_harm_language"],
        },
    ]
    output = io_out.getvalue()
    assert "Email address" in output
    assert "Telegram chat id or @username" in output


def test_configure_telegram_delivery_persists_escalation_contacts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    registry = ProfileRegistry(relic_home=tmp_path, hermes_profiles_home=tmp_path / "hermes")
    registry.create_subject("subj_001", "exp_001")
    registry.update_status("subj_001", "baseline_in_progress")
    registry.update_status("subj_001", "baseline_complete")
    registry.generate_gumi_background("subj_001", mode="random", seed=42)
    registry.update_status("subj_001", "gumi_seed_reviewed")
    registry.provision_hermes_profile("subj_001")
    monkeypatch.setenv("GUMI_SUBJ_001_TELEGRAM_BOT_TOKEN", "123456:telegram-token-test")
    contacts = [
        {"name": "Dr. Rossi", "method": "email", "value": "rossi@uni.it", "notify_on": ["all"]},
        {"name": "Dr. Rossi", "method": "telegram", "value": "123456789", "notify_on": ["all"]},
    ]

    profile, policy = registry.configure_telegram_delivery(
        "subj_001",
        telegram_bot_token_env="GUMI_SUBJ_001_TELEGRAM_BOT_TOKEN",
        telegram_user_id="123456789",
        escalation_contacts=contacts,
    )

    assert policy.escalation_contacts == contacts
    # Passive extraction is opt-in: provisioning must default it to OFF.
    assert policy.consent_for_passive_extraction is False
    assert '"method": "email"' in (profile.relic_subject_home / "delivery_policy.json").read_text(
        encoding="utf-8"
    )
    assert '"method": "telegram"' in (profile.relic_subject_home / "delivery_policy.json").read_text(
        encoding="utf-8"
    )
