from __future__ import annotations

from pathlib import Path

import pytest

from relic.profile.registry import ProfileRegistry


@pytest.fixture
def registry(tmp_path: Path) -> ProfileRegistry:
    return ProfileRegistry(
        relic_home=tmp_path / "relic",
        hermes_profiles_home=tmp_path / "hermes",
    )


def _prepare_reviewed_subject(registry: ProfileRegistry, subject_id: str = "subj_001") -> None:
    registry.create_subject(subject_id, "exp_001")
    registry.update_status(subject_id, "baseline_in_progress")
    registry.update_status(subject_id, "baseline_complete")
    registry.generate_gumi_background(subject_id, mode="random", seed=42)
    registry.update_status(subject_id, "gumi_seed_reviewed")


def test_provision_hermes_profile_installs_and_enables_relic_plugin(
    registry: ProfileRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, Path]] = []

    _prepare_reviewed_subject(registry)

    monkeypatch.setattr(
        "relic.profile.registry.install_relic_hermes_plugin",
        lambda hermes_home: calls.append(("install", hermes_home)) or {"status": "created"},
    )
    monkeypatch.setattr(
        "relic.profile.registry.enable_relic_hermes_plugin",
        lambda hermes_home: calls.append(("enable", hermes_home)) or {"status": "enabled"},
    )

    profile, _ = registry.provision_hermes_profile("subj_001")

    assert calls == [
        ("install", profile.hermes_home),
        ("enable", profile.hermes_home),
    ]


def test_provision_hermes_profile_keeps_provisioning_when_plugin_steps_fail(
    registry: ProfileRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _prepare_reviewed_subject(registry)

    monkeypatch.setattr(
        "relic.profile.registry.install_relic_hermes_plugin",
        lambda hermes_home: (_ for _ in ()).throw(RuntimeError("install failed")),
    )
    monkeypatch.setattr(
        "relic.profile.registry.enable_relic_hermes_plugin",
        lambda hermes_home: (_ for _ in ()).throw(RuntimeError("enable failed")),
    )

    profile, paths = registry.provision_hermes_profile("subj_001")

    assert profile.status == "hermes_profile_provisioned"
    assert paths["config"].is_file()
