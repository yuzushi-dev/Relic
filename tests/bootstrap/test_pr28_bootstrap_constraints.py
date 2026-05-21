"""Focused bootstrap constraint tests for enforced safety signals."""
from __future__ import annotations

import json
from pathlib import Path

from relic.bootstrap import build_pr28_bootstrap_outputs, subject_data_from_bootstrap_state


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_default_subject_keeps_careful_distancing_and_allows_challenge(tmp_path: Path) -> None:
    subject = subject_data_from_bootstrap_state(
        subject_id="subj_001",
        experiment_id="exp_001",
    )
    outputs = build_pr28_bootstrap_outputs(tmp_path, subject, generation_mode="hybrid", seed=9)
    constraints = _load(outputs["gumi_generation_constraints"])

    assert subject["boundary"]["careful_distancing_enabled"] is True
    assert constraints["relationship"]["challenge"] == "medium"
    assert constraints["relationship"]["challenge_allowed"] is True


def test_low_careful_distancing_acceptance_disables_it_when_anxiety_is_low() -> None:
    subject = subject_data_from_bootstrap_state(
        subject_id="subj_001",
        experiment_id="exp_001",
        state={
            "item_battery": {
                "scores": {
                    "project_calibration": {"careful_distancing_acceptance": 0.1},
                    "ecrrs": {"attachment_anxiety": 0.2},
                }
            }
        },
    )

    assert subject["boundary"]["careful_distancing_enabled"] is False


def test_high_attachment_anxiety_forces_careful_distancing_on_even_with_low_acceptance() -> None:
    subject = subject_data_from_bootstrap_state(
        subject_id="subj_001",
        experiment_id="exp_001",
        state={
            "item_battery": {
                "scores": {
                    "project_calibration": {"careful_distancing_acceptance": 0.1},
                    "ecrrs": {"attachment_anxiety": 0.7},
                }
            }
        },
    )

    assert subject["boundary"]["careful_distancing_enabled"] is True


def test_low_challenge_tolerance_disables_challenge(tmp_path: Path) -> None:
    subject = subject_data_from_bootstrap_state(
        subject_id="subj_001",
        experiment_id="exp_001",
        state={
            "item_battery": {
                "scores": {
                    "project_calibration": {"challenge_tolerance": 0.1},
                }
            }
        },
    )
    outputs = build_pr28_bootstrap_outputs(tmp_path, subject, generation_mode="hybrid", seed=10)
    constraints = _load(outputs["gumi_generation_constraints"])

    assert subject["interaction"]["challenge_tolerance"] == 0.1
    assert constraints["relationship"]["challenge"] == "low"
    assert constraints["relationship"]["challenge_allowed"] is False
