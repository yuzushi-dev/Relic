"""CLI tests for subject-specific Gumi and Hermes bootstrap commands."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from relic.profile.registry import ProfileRegistry


@pytest.fixture
def registry(tmp_path: Path) -> ProfileRegistry:
    return ProfileRegistry(
        relic_home=tmp_path / "relic",
        hermes_profiles_home=tmp_path / "hermes_profiles",
    )


@pytest.fixture
def patched_cli_registry(
    monkeypatch: pytest.MonkeyPatch, registry: ProfileRegistry
) -> ProfileRegistry:
    import relic.profile.cli as cli_module

    monkeypatch.setattr(cli_module, "ProfileRegistry", lambda: registry)
    return registry


def _create_baseline_complete_subject(registry: ProfileRegistry) -> None:
    registry.create_subject("subj_001", "exp_001")
    registry.update_status("subj_001", "baseline_in_progress")
    registry.update_status("subj_001", "baseline_complete")


def test_gumi_generate_writes_subject_and_hermes_workspace_files(
    patched_cli_registry: ProfileRegistry,
) -> None:
    from relic.profile.cli import profile_main

    _create_baseline_complete_subject(patched_cli_registry)

    rc = profile_main(["gumi", "generate", "subj_001", "--mode", "random", "--seed", "42"])

    assert rc == 0
    profile = patched_cli_registry.get_subject("subj_001")
    assert profile is not None
    assert profile.status == "gumi_seed_generated"
    subject_home = profile.relic_subject_home
    hermes_workspace = profile.hermes_home / "workspace" / "gumi"
    assert (subject_home / "gumi_background_profile.json").is_file()
    assert (subject_home / "gumi_seed_profile.json").is_file()
    assert (subject_home / "gumi_sweet_spot_config.json").is_file()
    assert (subject_home / "gumi_world.md").is_file()
    assert (subject_home / "gumi_relationship_policy.md").is_file()
    assert (subject_home / "gumi_social_graph.json").is_file()
    assert (subject_home / "gumi_visual_canon.json").is_file()
    assert (subject_home / "gumi_music_canon.json").is_file()
    assert (subject_home / "gumi_daily_rhythm.json").is_file()
    assert (hermes_workspace / "background.json").is_file()
    assert (hermes_workspace / "world.md").is_file()
    assert (hermes_workspace / "relationship_policy.md").is_file()

    background = json.loads((subject_home / "gumi_background_profile.json").read_text())
    assert background["subject_id"] == "subj_001"
    assert "identity" in background["domains"]
    assert "social_world" in background["domains"]


def test_hermes_provision_show_intro_compose_and_dry_run_send(
    patched_cli_registry: ProfileRegistry,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from relic.profile.cli import profile_main

    _create_baseline_complete_subject(patched_cli_registry)
    assert profile_main(["gumi", "generate", "subj_001", "--mode", "hybrid", "--seed", "7"]) == 0
    patched_cli_registry.update_status("subj_001", "gumi_seed_reviewed")

    assert profile_main(["hermes", "provision", "subj_001"]) == 0
    profile = patched_cli_registry.get_subject("subj_001")
    assert profile is not None
    assert profile.status == "hermes_profile_provisioned"
    assert (profile.hermes_home / "config.yaml").is_file()
    assert (profile.hermes_home / ".env").is_file()
    config_text = (profile.hermes_home / "config.yaml").read_text(encoding="utf-8")
    assert "provider: custom" in config_text
    assert "base_url: http://localhost:11434/v1" in config_text
    assert "default: qwen3.5:cloud" in config_text
    assert "provider: hindsight" in config_text
    assert "provider_mode: tools" in config_text
    assert "namespace: gumi-subj_001" in config_text
    assert "exposure_logging: true" in config_text
    assert "tool_use_enforcement: true" in config_text
    assert "redact_pii: true" in config_text

    capsys.readouterr()
    assert profile_main(["hermes", "show", "subj_001"]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["profile_name"] == "gumi-subj_001"
    assert shown["exists"] is True

    assert profile_main(["gumi", "intro", "compose", "subj_001", "--seed", "11"]) == 0
    profile = patched_cli_registry.get_subject("subj_001")
    assert profile is not None
    assert profile.status == "intro_composed"
    intro_path = profile.relic_subject_home / "gumi_intro_message.json"
    intro_event = json.loads(intro_path.read_text())
    assert intro_event["status"] == "composed"
    assert intro_event["message_text_local_ref"].startswith("local-only:")
    assert "message_text" not in intro_event

    assert profile_main(["gumi", "intro", "send", "subj_001", "--dry-run"]) == 0
    profile = patched_cli_registry.get_subject("subj_001")
    assert profile is not None
    assert profile.status == "intro_sent"
    sent_event = json.loads(intro_path.read_text())
    assert sent_event["status"] == "sent"
    assert sent_event["researcher_previewed"] is True


def test_telegram_cron_media_and_delivery_cli_use_hermes_native_artifacts(
    patched_cli_registry: ProfileRegistry,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from relic.profile.cli import profile_main

    monkeypatch.setenv("GUMI_SUBJ_001_TELEGRAM_BOT_TOKEN", "123456:telegram-token-test")
    _create_baseline_complete_subject(patched_cli_registry)
    assert profile_main(["gumi", "generate", "subj_001", "--mode", "hybrid", "--seed", "7"]) == 0
    patched_cli_registry.update_status("subj_001", "gumi_seed_reviewed")
    assert profile_main(["hermes", "provision", "subj_001"]) == 0

    assert profile_main(
        [
            "hermes",
            "configure-telegram",
            "subj_001",
            "--bot-token-env",
            "GUMI_SUBJ_001_TELEGRAM_BOT_TOKEN",
            "--telegram-user-id",
            "123456789",
        ]
    ) == 0
    profile = patched_cli_registry.get_subject("subj_001")
    assert profile is not None
    env_text = (profile.hermes_home / ".env").read_text(encoding="utf-8")
    assert "TELEGRAM_ALLOWED_USERS=123456789" in env_text
    assert "TELEGRAM_HOME_CHANNEL=telegram:123456789" in env_text

    assert profile_main(["gumi", "media", "generate", "subj_001", "--seed", "3"]) == 0
    assert (profile.relic_subject_home / "gumi_voice_canon.json").is_file()
    assert (profile.hermes_home / "workspace" / "gumi" / "lyria_canon.json").is_file()

    assert profile_main(
        ["hermes", "cron", "provision", "subj_001", "--maintenance", "--initiative", "--media", "--dry-run"]
    ) == 0
    initiative_text = (profile.hermes_home / "cron" / "initiative.yaml").read_text(encoding="utf-8")
    assert "target: telegram:123456789" in initiative_text

    assert profile_main(["gumi", "intro", "compose", "subj_001", "--seed", "11"]) == 0
    assert profile_main(["gumi", "intro", "send", "subj_001", "--deliver"]) == 0
    out = capsys.readouterr().out
    assert "Prepared Hermes delivery" in out
    assert "Target: telegram:123456789" in out
    current = patched_cli_registry.get_subject("subj_001")
    assert current is not None
    assert current.status == "intro_composed"


def test_validate_checks_required_gumi_and_hermes_artifacts(
    patched_cli_registry: ProfileRegistry,
) -> None:
    from relic.profile.cli import profile_main

    _create_baseline_complete_subject(patched_cli_registry)
    assert profile_main(["gumi", "generate", "subj_001", "--mode", "random", "--seed", "42"]) == 0
    patched_cli_registry.update_status("subj_001", "gumi_seed_reviewed")
    assert profile_main(["hermes", "provision", "subj_001"]) == 0
    assert profile_main(["gumi", "intro", "compose", "subj_001", "--seed", "9"]) == 0

    valid, errors = patched_cli_registry.validate_subject("subj_001")
    assert valid is True
    assert errors == []

    profile = patched_cli_registry.get_subject("subj_001")
    assert profile is not None
    (profile.hermes_home / "config.yaml").unlink()
    valid, errors = patched_cli_registry.validate_subject("subj_001")
    assert valid is False
    assert any("Missing Hermes profile artifact: config.yaml" in e for e in errors)
