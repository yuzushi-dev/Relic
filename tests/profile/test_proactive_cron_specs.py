"""Focused cron spec tests for proactive provisioning.

These stay outside the ignored runtime_provisioning module so the default
profile test suite still covers the new proactive family contract.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

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


def test_proactive_cron_family_has_three_jobs_and_local_delivery_default(
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
    assert "deliver_target: local" in proactive_text
    assert "deliver_target_env: RELIC_PROACTIVE_DELIVER_TARGET" in proactive_text

    manifest = json.loads((profile.relic_subject_home / "gumi_cron_manifest.json").read_text(encoding="utf-8"))
    commands = manifest["install_commands"]
    gate_cmd = next(c for c in commands if "--name \"subj_001_proactive_gate\"" in c)
    message_cmd = next(c for c in commands if "--name \"subj_001_proactive_message\"" in c)
    dispatch_cmd = next(c for c in commands if "--name \"subj_001_proactive_dispatch\"" in c)

    assert "--no-agent" in gate_cmd and "--deliver" not in gate_cmd
    assert "--deliver \"local\"" in message_cmd
    assert "--no-agent" in dispatch_cmd and "--deliver" not in dispatch_cmd
    assert (profile.hermes_home / "scripts" / "subj_001" / "relic_proactive_dispatch.sh").is_file()


def test_diegetic_cron_family_stays_unchanged_as_control(
    registry: ProfileRegistry,
) -> None:
    _bootstrap_subject(registry)

    profile, paths = registry.provision_subject_cron_specs(
        "subj_001",
        families=["diegetic"],
        dry_run=True,
    )

    diegetic_text = paths["diegetic"].read_text(encoding="utf-8")
    assert "family: diegetic" in diegetic_text
    assert "id: subj_001_diegetic_gate" in diegetic_text
    assert "id: subj_001_diegetic_message" in diegetic_text
    assert "id: subj_001_diegetic_dispatch" in diegetic_text
    assert "deliver_target: local" in diegetic_text
    assert "deliver_target_env: RELIC_DIEGETIC_DELIVER_TARGET" in diegetic_text

    manifest = json.loads((profile.relic_subject_home / "gumi_cron_manifest.json").read_text(encoding="utf-8"))
    commands = manifest["install_commands"]
    gate_cmd = next(c for c in commands if "--name \"subj_001_diegetic_gate\"" in c)
    message_cmd = next(c for c in commands if "--name \"subj_001_diegetic_message\"" in c)
    dispatch_cmd = next(c for c in commands if "--name \"subj_001_diegetic_dispatch\"" in c)

    assert "--no-agent" in gate_cmd and "--deliver" not in gate_cmd
    assert "--deliver \"local\"" in message_cmd
    assert "--no-agent" in dispatch_cmd and "--deliver" not in dispatch_cmd


def test_initiative_cron_family_stays_unchanged_as_control(
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
