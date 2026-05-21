"""Tests for Hermes human-delay config rendering."""

from __future__ import annotations

import json
from pathlib import Path

from relic.hermes_runtime import (
    absence_tolerance_to_human_delay,
    absence_tolerance_to_send_delay,
    render_subject_hermes_config,
)
from relic.profile.registry import ProfileRegistry


def test_absence_tolerance_to_human_delay_preserves_default_is_monotonic_and_clamped() -> None:
    assert absence_tolerance_to_human_delay(0.5) == (800, 2500)

    lower = absence_tolerance_to_human_delay(0.1)
    higher = absence_tolerance_to_human_delay(0.9)
    assert lower[0] < higher[0]
    assert lower[1] < higher[1]

    assert absence_tolerance_to_human_delay(-10.0) == (0, 0)
    assert absence_tolerance_to_human_delay(10.0) == (5000, 15000)


def test_absence_tolerance_to_send_delay_uses_expected_buckets() -> None:
    assert absence_tolerance_to_send_delay(0.0) == "1m"
    assert absence_tolerance_to_send_delay(0.19) == "1m"
    assert absence_tolerance_to_send_delay(0.2) == "5m"
    assert absence_tolerance_to_send_delay(0.39) == "5m"
    assert absence_tolerance_to_send_delay(0.4) == "15m"
    assert absence_tolerance_to_send_delay(0.59) == "15m"
    assert absence_tolerance_to_send_delay(0.6) == "45m"
    assert absence_tolerance_to_send_delay(0.79) == "45m"
    assert absence_tolerance_to_send_delay(0.8) == "2h"
    assert absence_tolerance_to_send_delay(1.0) == "2h"


def test_render_subject_hermes_config_uses_custom_mode_and_helper_values() -> None:
    config = render_subject_hermes_config(
        profile_name="gumi-subj_001",
        subject_id="subj_001",
        absence_tolerance=0.8,
    )

    min_ms, max_ms = absence_tolerance_to_human_delay(0.8)

    assert "human_delay:" in config
    assert "  mode: custom" in config
    assert f"  min_ms: {min_ms}" in config
    assert f"  max_ms: {max_ms}" in config


def test_render_subject_hermes_config_default_preserves_current_delay_values() -> None:
    config = render_subject_hermes_config(
        profile_name="gumi-subj_001",
        subject_id="subj_001",
    )

    assert "  mode: custom" in config
    assert "  min_ms: 800" in config
    assert "  max_ms: 2500" in config


def test_provision_hermes_profile_uses_baseline_absence_tolerance(tmp_path: Path) -> None:
    registry = ProfileRegistry(
        relic_home=tmp_path / "relic",
        hermes_profiles_home=tmp_path / "hermes",
    )
    registry.create_subject("subj_001", "exp_001")
    registry.update_status("subj_001", "baseline_in_progress")
    registry.update_status("subj_001", "baseline_complete")
    profile, _ = registry.generate_gumi_background("subj_001", mode="random", seed=42)
    registry.update_status("subj_001", "gumi_seed_reviewed")

    (profile.relic_subject_home / "baseline_user_profile.json").write_text(
        json.dumps(
            {
                "item_battery": {
                    "scores": {
                        "project_calibration": {
                            "gumi_absence_tolerance": 0.8,
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    provisioned, _ = registry.provision_hermes_profile("subj_001")
    config_text = (provisioned.hermes_home / "config.yaml").read_text(encoding="utf-8")
    min_ms, max_ms = absence_tolerance_to_human_delay(0.8)

    assert "  mode: custom" in config_text
    assert f"  min_ms: {min_ms}" in config_text
    assert f"  max_ms: {max_ms}" in config_text
