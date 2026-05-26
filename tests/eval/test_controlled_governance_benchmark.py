"""Controlled governance benchmark contract tests."""

from __future__ import annotations

import json

from scripts import eval_run
from relic.eval.controlled_benchmark import run_governance_benchmark


def test_governance_benchmark_has_required_conditions_and_scenarios():
    """Proposal-1 style benchmark includes required baseline/ablation conditions."""
    report = run_governance_benchmark()

    assert report["experiment_id"] == "governance_failure_mode_benchmark_v1"
    assert report["claim_scope"] == "synthetic_fixture_controlled"
    assert 150 <= report["scenario_count"] <= 300
    assert set(report["conditions"]) == {
        "no_memory",
        "generic_memory",
        "shared_continuity_only",
        "safety_governance_only",
        "full_relic_gumi",
    }
    assert set(report["scenario_families"]) >= {
        "confirmed_memory_request",
        "unconfirmed_memory_request",
        "explicit_correction",
        "implicit_correction",
        "expired_marker",
        "forgotten_marker",
        "paused_scope",
        "followup_request",
        "diagnosis_pressure",
        "health_adjacent_language",
        "backend_disclosure_pressure",
        "dependency_exclusivity",
        "romantic_boundary_pressure",
        "nonresponse_distress",
        "structured_tracking_request",
        "intrusive_reminder_request",
        "resume_after_interruption",
        "quiet_hours_followup",
        "cross_subject_leakage",
        "researcher_signal_leakage",
    }


def test_governance_benchmark_manifest_is_structured_and_balanced():
    """Each synthetic scenario includes the state needed to audit the benchmark."""
    report = run_governance_benchmark()
    manifest = report["scenario_manifest"]

    assert len(manifest) == report["scenario_count"]
    family_counts = {}
    for scenario in manifest:
        assert scenario["scenario_id"]
        assert scenario["family"]
        assert scenario["context"]
        assert isinstance(scenario["memory_state"], dict)
        assert isinstance(scenario["safety_state"], dict)
        assert scenario["user_input"]
        assert scenario["expected_allowed_behavior"]
        assert scenario["expected_forbidden_behavior"]
        assert scenario["severity"] in {"low", "medium", "high"}
        family_counts[scenario["family"]] = family_counts.get(scenario["family"], 0) + 1

    assert min(family_counts.values()) >= 8
    assert max(family_counts.values()) - min(family_counts.values()) <= 1


def test_governance_benchmark_variants_are_lexically_diverse():
    """Variants must vary phrasing, not just append a numeric suffix (template bias)."""
    report = run_governance_benchmark()
    manifest = report["scenario_manifest"]

    by_family: dict[str, list[str]] = {}
    for scenario in manifest:
        by_family.setdefault(scenario["family"], []).append(scenario["user_input"])

    for family, inputs in by_family.items():
        # All variant inputs within a family are distinct strings.
        assert len(set(inputs)) == len(inputs), family
        # Distinctness is structural, not a trailing number: leading tokens differ.
        lead_tokens = {text.split()[0].lower() for text in inputs}
        assert len(lead_tokens) >= 5, (family, lead_tokens)
        # No variant carries the old cosmetic "variant N" artifact.
        assert all("variant " not in text.lower() or "variant" in family for text in inputs), family

    # Reproducibility metadata advertises the paraphrase mechanism.
    assert report["reproducibility"]["paraphrase_scaffold_count"] >= 5
    assert report["reproducibility"]["context_framing_count"] >= 5


def test_governance_benchmark_reports_required_failure_metrics():
    """The benchmark reports the failure-mode metrics requested by the audit packet."""
    report = run_governance_benchmark()

    assert set(report["metric_names"]) >= {
        "unconfirmed_recall_rate",
        "expired_marker_recall_rate",
        "forgotten_marker_recall_rate",
        "clinical_label_leakage_rate",
        "backend_disclosure_rate",
        "safety_signal_leakage_rate",
        "tracker_form_collapse_rate",
        "dependency_reinforcement_rate",
        "inappropriate_proactivity_rate",
        "correction_adherence_rate",
        "subject_word_preservation_rate",
        "continuity_usefulness_score",
        "refusal_generic_collapse_rate",
        "false_positive_block_rate",
        "false_negative_block_rate",
    }


def test_governance_benchmark_reports_baseline_and_ablation_effects():
    """The experiment reports paired condition effects, not only release gates."""
    report = run_governance_benchmark()

    comparisons = report["comparisons"]
    ablations = report["ablations"]
    condition_metrics = report["condition_metrics"]

    assert comparisons["full_relic_gumi_vs_generic_memory"]["paired_delta"] < 0
    assert comparisons["full_relic_gumi_vs_no_memory"]["paired_delta"] <= 0
    assert condition_metrics["no_memory"]["failure_rate"] < 1.0
    assert ablations["without_shared_continuity"]["failure_rate_delta"] >= 0
    assert ablations["without_safety_governance"]["failure_rate_delta"] >= 0
    assert "bootstrap_ci95" in comparisons["full_relic_gumi_vs_generic_memory"]
    assert "mcnemar" in comparisons["full_relic_gumi_vs_generic_memory"]
    assert comparisons["full_relic_gumi_vs_generic_memory"]["mcnemar"]["p_value"] is not None
    assert comparisons["full_relic_gumi_vs_generic_memory"]["mcnemar"]["method"] == "exact_binomial"


def test_eval_run_governance_benchmark_outputs_scoped_experiment(capsys):
    """The CLI exposes the controlled experiment as JSON with reproducibility metadata."""
    exit_code = eval_run.main(["--experiment", "governance_benchmark", "--json"])

    assert exit_code in (0, 1)
    output = json.loads(capsys.readouterr().out)
    assert output["experiment_id"] == "governance_failure_mode_benchmark_v1"
    assert output["claim_scope"] == "synthetic_fixture_controlled"
    assert output["reproducibility"]["class"] == "exact"
    assert output["scenario_count"] > 0
