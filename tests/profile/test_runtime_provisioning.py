"""Tests for subject runtime provisioning features."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.slow

from relic.profile.registry import ProfileRegistry


@pytest.fixture
def registry(tmp_path: Path) -> ProfileRegistry:
    return ProfileRegistry(
        relic_home=tmp_path / "relic",
        hermes_profiles_home=tmp_path / "hermes",
    )


def _bootstrap_subject(registry: ProfileRegistry) -> None:
    registry.create_subject("subj_001", "exp_001")
    registry.update_status("subj_001", "baseline_in_progress")
    registry.update_status("subj_001", "baseline_complete")
    registry.generate_gumi_background("subj_001", mode="random", seed=42)
    registry.update_status("subj_001", "gumi_seed_reviewed")
    registry.provision_hermes_profile("subj_001")


def _bootstrap_named_subject(registry: ProfileRegistry, subject_id: str) -> None:
    registry.create_subject(subject_id, "exp_001")
    registry.update_status(subject_id, "baseline_in_progress")
    registry.update_status(subject_id, "baseline_complete")
    registry.generate_gumi_background(subject_id, mode="random", seed=42)
    registry.update_status(subject_id, "gumi_seed_reviewed")
    registry.provision_hermes_profile(subject_id)


def test_configure_telegram_delivery_writes_private_env_and_redacted_policy(
    registry: ProfileRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bootstrap_subject(registry)
    monkeypatch.setenv("GUMI_SUBJ_001_TELEGRAM_BOT_TOKEN", "123456:telegram-token-test")

    profile, policy = registry.configure_telegram_delivery(
        "subj_001",
        telegram_bot_token_env="GUMI_SUBJ_001_TELEGRAM_BOT_TOKEN",
        telegram_user_id="123456789",
        consent_for_generated_images=True,
        consent_for_generated_audio=True,
        consent_for_generated_music=False,
    )

    assert profile.subject_id == "subj_001"
    assert policy.delivery_enabled is True
    env_text = (profile.hermes_home / ".env").read_text(encoding="utf-8")
    assert "TELEGRAM_BOT_TOKEN=123456:telegram-token-test" in env_text
    assert "TELEGRAM_ALLOWED_USERS=123456789" in env_text
    assert "TELEGRAM_HOME_CHANNEL=telegram:123456789" in env_text
    assert "GUMI_TELEGRAM_BOT_TOKEN_ENV=GUMI_SUBJ_001_TELEGRAM_BOT_TOKEN" in env_text
    assert "GUMI_DELIVERY_CHANNEL=telegram" in env_text

    policy_data = json.loads((profile.relic_subject_home / "delivery_policy.json").read_text(encoding="utf-8"))
    assert policy_data["telegram_user_id_hash"] != "123456789"
    assert policy_data["telegram_user_id_display"].startswith("telegram:")
    assert "123456:telegram-token-test" not in json.dumps(policy_data)
    allowlist_data = json.loads((profile.relic_subject_home / "delivery_allowlist.json").read_text(encoding="utf-8"))
    assert allowlist_data["allowlist"][0]["platform"] == "telegram"
    assert allowlist_data["allowlist"][0]["enabled"] is True
    assert allowlist_data["allowlist"][0]["target_hash"] == policy_data["telegram_user_id_hash"]
    assert "123456789" not in json.dumps(allowlist_data)
    assert "123456:telegram-token-test" not in json.dumps(allowlist_data)


def test_configure_telegram_delivery_writes_system_message_suppression_keys(
    registry: ProfileRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Provisioning writes HERMES_SUPPRESS_SYSTEM_MESSAGES and TELEGRAM_ADMIN_CHANNEL (I5)."""
    _bootstrap_subject(registry)
    monkeypatch.setenv("GUMI_SUBJ_001_TELEGRAM_BOT_TOKEN", "123456:telegram-token-test")

    profile, _ = registry.configure_telegram_delivery(
        "subj_001",
        telegram_bot_token_env="GUMI_SUBJ_001_TELEGRAM_BOT_TOKEN",
        telegram_user_id="123456789",
        consent_for_generated_images=False,
        consent_for_generated_audio=False,
        consent_for_generated_music=False,
    )

    env_text = (profile.hermes_home / ".env").read_text(encoding="utf-8")
    assert "HERMES_SUPPRESS_SYSTEM_MESSAGES=true" in env_text
    assert "TELEGRAM_ADMIN_CHANNEL=" in env_text


def test_configure_telegram_delivery_rejects_reusing_user_or_bot_across_subjects(
    registry: ProfileRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bootstrap_named_subject(registry, "subj_001")
    _bootstrap_named_subject(registry, "subj_002")
    monkeypatch.setenv("GUMI_SUBJ_001_TELEGRAM_BOT_TOKEN", "111111:subject-one-token")
    monkeypatch.setenv("GUMI_SUBJ_002_TELEGRAM_BOT_TOKEN", "222222:subject-two-token")

    registry.configure_telegram_delivery(
        "subj_001",
        telegram_bot_token_env="GUMI_SUBJ_001_TELEGRAM_BOT_TOKEN",
        telegram_user_id="111111111",
    )

    with pytest.raises(ValueError, match="Telegram user id is already assigned"):
        registry.configure_telegram_delivery(
            "subj_002",
            telegram_bot_token_env="GUMI_SUBJ_002_TELEGRAM_BOT_TOKEN",
            telegram_user_id="111111111",
        )

    with pytest.raises(ValueError, match="Telegram bot token env is already assigned"):
        registry.configure_telegram_delivery(
            "subj_002",
            telegram_bot_token_env="GUMI_SUBJ_001_TELEGRAM_BOT_TOKEN",
            telegram_user_id="222222222",
        )

    monkeypatch.setenv("GUMI_SUBJ_002_TELEGRAM_BOT_TOKEN", "111111:subject-one-token")
    with pytest.raises(ValueError, match="Telegram bot token is already assigned"):
        registry.configure_telegram_delivery(
            "subj_002",
            telegram_bot_token_env="GUMI_SUBJ_002_TELEGRAM_BOT_TOKEN",
            telegram_user_id="222222222",
        )

    monkeypatch.setenv("GUMI_SUBJ_002_TELEGRAM_BOT_TOKEN", "222222:subject-two-token")
    profile, _ = registry.configure_telegram_delivery(
        "subj_002",
        telegram_bot_token_env="GUMI_SUBJ_002_TELEGRAM_BOT_TOKEN",
        telegram_user_id="222222222",
    )
    assert profile.hermes_profile_name == "gumi-subj_002"


def test_generate_gumi_media_canon_writes_visual_voice_and_lyria(
    registry: ProfileRegistry,
) -> None:
    _bootstrap_subject(registry)

    profile, canon, paths = registry.generate_gumi_media_canon("subj_001", seed=7)

    assert profile.subject_id == "subj_001"
    assert canon.subject_id == "subj_001"
    assert paths["visual"].is_file()
    assert paths["voice"].is_file()
    assert paths["lyria"].is_file()
    assert paths["policy"].is_file()
    workspace = profile.hermes_home / "workspace" / "gumi"
    assert (workspace / "visual_canon.json").is_file()
    assert (workspace / "voice_canon.json").is_file()
    assert (workspace / "lyria_canon.json").is_file()
    assert (workspace / "media_policy.json").is_file()


def test_provision_subject_cron_specs_creates_family_specs(
    registry: ProfileRegistry,
) -> None:
    _bootstrap_subject(registry)
    registry.configure_telegram_delivery(
        "subj_001",
        telegram_bot_token_env="GUMI_SUBJ_001_TELEGRAM_BOT_TOKEN",
        telegram_user_id="123456789",
    )

    profile, paths = registry.provision_subject_cron_specs(
        "subj_001",
        families=["maintenance", "initiative", "media"],
        dry_run=True,
    )

    assert profile.subject_id == "subj_001"
    assert "maintenance" in paths
    assert "initiative" in paths
    assert "media" in paths
    assert (profile.hermes_home / "cron" / "install_manifest.json").is_file()
    manifest = json.loads((profile.relic_subject_home / "gumi_cron_manifest.json").read_text(encoding="utf-8"))
    assert manifest["families"] == ["maintenance", "initiative", "media"]
    assert manifest["hermes_native"] is True
    assert manifest["install_strategy"] == "hermes cron create"
    assert any("--deliver \"telegram:123456789\"" in command for command in manifest["install_commands"])
    initiative_text = paths["initiative"].read_text(encoding="utf-8")
    assert "target: telegram:123456789" in initiative_text
    assert "send_message" not in initiative_text


def test_prepare_intro_delivery_uses_hermes_native_target_and_local_message(
    registry: ProfileRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bootstrap_subject(registry)
    monkeypatch.setenv("GUMI_SUBJ_001_TELEGRAM_BOT_TOKEN", "123456:telegram-token-test")
    registry.configure_telegram_delivery(
        "subj_001",
        telegram_bot_token_env="GUMI_SUBJ_001_TELEGRAM_BOT_TOKEN",
        telegram_user_id="123456789",
    )
    profile = registry.get_subject("subj_001")
    assert profile is not None
    event = {
        "subject_id": "subj_001",
        "message_id": "intro_abc123",
        "status": "composed",
        "message_text_hash": "dummy",
        "message_text_local_ref": "local-only:intro_abc123.txt",
    }
    (profile.relic_subject_home / "gumi_intro_message.json").write_text(json.dumps(event), encoding="utf-8")
    local_only = profile.relic_subject_home / "local_only"
    local_only.mkdir()
    (local_only / "intro_abc123.txt").write_text("Ciao da Gumi.", encoding="utf-8")
    registry.update_status("subj_001", "intro_composed")

    decision = registry.prepare_intro_delivery("subj_001")

    assert decision["status"] == "delivery_ready"
    assert decision["target"] == "telegram:123456789"
    assert decision["delivery_backend"] == "hermes"
    assert "hermes send telegram:123456789" in decision["hermes_command_preview"]
    log_text = (profile.relic_subject_home / "delivery_decision_log.jsonl").read_text(encoding="utf-8")
    assert "Ciao da Gumi" not in log_text


def test_validate_subject_accepts_core_bootstrap_without_optional_runtime_extensions(
    registry: ProfileRegistry,
) -> None:
    _bootstrap_subject(registry)
    valid, errors = registry.validate_subject("subj_001")
    assert valid is True
    assert errors == []


def test_each_subject_profile_uses_private_hindsight_memory_provider(
    registry: ProfileRegistry,
) -> None:
    _bootstrap_named_subject(registry, "subj_001")
    _bootstrap_named_subject(registry, "subj_002")

    first = registry.get_subject("subj_001")
    second = registry.get_subject("subj_002")
    assert first is not None
    assert second is not None

    first_config = (first.hermes_home / "config.yaml").read_text(encoding="utf-8")
    second_config = (second.hermes_home / "config.yaml").read_text(encoding="utf-8")

    assert "provider: hindsight" in first_config
    assert "provider: hindsight" in second_config
    assert "provider_mode: tools" in first_config
    assert "provider_mode: tools" in second_config
    assert "namespace: gumi-subj_001" in first_config
    assert "namespace: gumi-subj_002" in second_config
    assert "exposure_logging: true" in first_config
    assert "exposure_logging: true" in second_config
    assert first.hermes_home != second.hermes_home
    assert "HINDSIGHT_LLM_API_KEY_ENV" not in (first.hermes_home / ".env").read_text()
    assert "HINDSIGHT_LLM_API_KEY_ENV" not in (second.hermes_home / ".env").read_text()

    first_hindsight = json.loads((first.hermes_home / "hindsight" / "config.json").read_text())
    second_hindsight = json.loads((second.hermes_home / "hindsight" / "config.json").read_text())
    assert first_hindsight["mode"] == "local"
    assert second_hindsight["mode"] == "local"
    assert first_hindsight["llm_provider"] == "ollama"
    assert second_hindsight["llm_provider"] == "ollama"
    assert first_hindsight["base_url"] == "http://localhost:11434/v1"
    assert second_hindsight["base_url"] == "http://localhost:11434/v1"
    assert first_hindsight["model"] == "qwen3.5:cloud"
    assert second_hindsight["model"] == "qwen3.5:cloud"
    assert "llm_api_key_env" not in first_hindsight
    assert "llm_api_key_env" not in second_hindsight
    assert first_hindsight["bank_id"] == "gumi-subj_001"
    assert second_hindsight["bank_id"] == "gumi-subj_002"
    assert first_hindsight["memory_mode"] == "tools"
    assert second_hindsight["memory_mode"] == "tools"


def test_provision_subject_cron_specs_includes_memory_sync_job(
    registry: ProfileRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bootstrap_subject(registry)
    monkeypatch.setenv("GUMI_SUBJ_001_TELEGRAM_BOT_TOKEN", "123456:telegram-token-test")
    registry.configure_telegram_delivery(
        "subj_001",
        telegram_bot_token_env="GUMI_SUBJ_001_TELEGRAM_BOT_TOKEN",
        telegram_user_id="123456789",
    )

    profile, paths = registry.provision_subject_cron_specs(
        "subj_001",
        families=["initiative"],
        dry_run=True,
    )

    manifest_path = profile.relic_subject_home / "gumi_cron_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    commands = manifest["install_commands"]
    # Check memory_sync job is present in commands
    mem_commands = [c for c in commands if "memory_sync" in c]
    assert len(mem_commands) == 1, f"Expected 1 memory_sync command, got {len(mem_commands)}: {mem_commands}"

    mem_cmd = mem_commands[0]
    # Must be --no-agent
    assert "--no-agent" in mem_cmd
    # Must include --script with memory_sync.sh
    assert "relic_memory_sync.sh" in mem_cmd
    # Must NOT have --deliver (local target)
    assert "--deliver" not in mem_cmd
    # Schedule offset
    assert "2-59/30" in mem_cmd


def test_memory_sync_cron_job_no_deliver_for_local_target(
    registry: ProfileRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify memory_sync (local no-agent) does not get --deliver in rendered command."""
    _bootstrap_subject(registry)
    monkeypatch.setenv("GUMI_SUBJ_001_TELEGRAM_BOT_TOKEN", "123456:telegram-token-test")
    registry.configure_telegram_delivery(
        "subj_001",
        telegram_bot_token_env="GUMI_SUBJ_001_TELEGRAM_BOT_TOKEN",
        telegram_user_id="123456789",
    )

    profile, _ = registry.provision_subject_cron_specs(
        "subj_001",
        families=["maintenance", "initiative"],
        dry_run=True,
    )

    manifest_path = profile.relic_subject_home / "gumi_cron_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    # memory_sync must have --no-agent and no --deliver
    mem_cmds = [c for c in manifest["install_commands"] if "subj_001_memory_sync" in c]
    assert len(mem_cmds) == 1, f"Expected 1 memory_sync command: {mem_cmds}"
    assert "--no-agent" in mem_cmds[0]
    assert "--deliver" not in mem_cmds[0]


def test_provision_subject_cron_specs_adds_diegetic_family_with_local_delivery_by_default(
    registry: ProfileRegistry,
) -> None:
    _bootstrap_subject(registry)

    profile, paths = registry.provision_subject_cron_specs(
        "subj_001",
        families=["diegetic"],
        dry_run=True,
    )

    assert "diegetic" in paths
    diegetic_text = paths["diegetic"].read_text(encoding="utf-8")
    assert "family: diegetic" in diegetic_text
    assert "id: subj_001_diegetic_gate" in diegetic_text
    assert "id: subj_001_diegetic_message" in diegetic_text
    assert "id: subj_001_diegetic_dispatch" in diegetic_text
    assert "target: local" in diegetic_text

    manifest = json.loads((profile.relic_subject_home / "gumi_cron_manifest.json").read_text(encoding="utf-8"))
    commands = manifest["install_commands"]
    gate_cmd = next(c for c in commands if "--name \"subj_001_diegetic_gate\"" in c)
    message_cmd = next(c for c in commands if "--name \"subj_001_diegetic_message\"" in c)
    dispatch_cmd = next(c for c in commands if "--name \"subj_001_diegetic_dispatch\"" in c)

    assert "--no-agent" in gate_cmd and "--deliver" not in gate_cmd
    assert "--deliver \"local\"" in message_cmd
    assert "--no-agent" in dispatch_cmd and "--deliver" not in dispatch_cmd
    assert (profile.hermes_home / "scripts" / "subj_001" / "relic_diegetic_dispatch.sh").is_file()


def test_provision_subject_cron_specs_adds_proactive_family_with_local_delivery_by_default(
    registry: ProfileRegistry,
) -> None:
    _bootstrap_subject(registry)

    profile, paths = registry.provision_subject_cron_specs(
        "subj_001",
        families=["proactive"],
        dry_run=True,
    )

    assert "proactive" in paths
    proactive_text = paths["proactive"].read_text(encoding="utf-8")
    assert "family: proactive" in proactive_text
    assert "id: subj_001_proactive_gate" in proactive_text
    assert "id: subj_001_proactive_message" in proactive_text
    assert "id: subj_001_proactive_dispatch" in proactive_text
    assert "target: local" in proactive_text

    manifest = json.loads((profile.relic_subject_home / "gumi_cron_manifest.json").read_text(encoding="utf-8"))
    commands = manifest["install_commands"]
    gate_cmd = next(c for c in commands if "--name \"subj_001_proactive_gate\"" in c)
    message_cmd = next(c for c in commands if "--name \"subj_001_proactive_message\"" in c)
    dispatch_cmd = next(c for c in commands if "--name \"subj_001_proactive_dispatch\"" in c)

    assert "--no-agent" in gate_cmd and "--deliver" not in gate_cmd
    assert "--deliver \"local\"" in message_cmd
    assert "--no-agent" in dispatch_cmd and "--deliver" not in dispatch_cmd
    assert (profile.hermes_home / "scripts" / "subj_001" / "relic_proactive_dispatch.sh").is_file()


def test_provision_subject_cron_specs_keeps_initiative_jobs_unchanged(
    registry: ProfileRegistry,
) -> None:
    _bootstrap_subject(registry)
    registry.configure_telegram_delivery(
        "subj_001",
        telegram_bot_token_env="GUMI_SUBJ_001_TELEGRAM_BOT_TOKEN",
        telegram_user_id="123456789",
    )

    profile, _ = registry.provision_subject_cron_specs(
        "subj_001",
        families=["initiative"],
        dry_run=True,
    )

    manifest = json.loads((profile.relic_subject_home / "gumi_cron_manifest.json").read_text(encoding="utf-8"))
    commands = manifest["install_commands"]
    assert any("--name \"subj_001_checkin_gate\"" in c for c in commands)
    assert any("--name \"subj_001_checkin_message\"" in c for c in commands)
    assert any("--name \"subj_001_checkin_dispatch\"" in c for c in commands)
    assert not any("diegetic" in c for c in commands)
    assert not any("proactive" in c for c in commands)
