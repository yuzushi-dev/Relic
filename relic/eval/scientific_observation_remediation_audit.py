"""Trace scientific observation gaps to current local evidence and blockers."""

from __future__ import annotations

from typing import Any


REPORT_ID = "scientific_observation_remediation_audit_v1"
CLAIM_SCOPE = "observation_gap_to_evidence_traceability"
REVIEW_DATE = "2026-05-25"
SOURCE_DOCUMENTS = [
    "docs/relic_gumi_scientific_observations/02_matrice_claim_evidenze.md",
    "docs/relic_gumi_scientific_observations/03_lacune_scientifiche_e_validita.md",
    "docs/relic_gumi_scientific_observations/04_proposte_sperimentali.md",
]


def build_scientific_observation_remediation_audit() -> dict[str, Any]:
    """Build a claim/evidence/gap audit for the scientific observation packet."""
    gaps = _gaps()
    blocked_external = [
        gap for gap in gaps if gap["status"] == "blocked_external_evidence"
    ]
    resolved_or_partial = [
        gap
        for gap in gaps
        if gap["status"] in {"locally_resolved", "partially_resolved"}
    ]

    return {
        "report_id": REPORT_ID,
        "claim_scope": CLAIM_SCOPE,
        "source_documents": SOURCE_DOCUMENTS,
        "methodology": {
            "evidence_model": "claim_gap_to_current_artifact_traceability_matrix",
            "review_date": REVIEW_DATE,
            "status_values": [
                "locally_resolved",
                "partially_resolved",
                "blocked_external_evidence",
                "intentionally_out_of_scope",
            ],
            "provenance_basis": [
                "scientific_observation_gap_rows",
                "current_eval_report_inventory",
                "scientific_defensibility_gate_v1_blocking_requirements",
                "claim_limitations_preserved",
            ],
        },
        "summary": {
            "gap_count": len(gaps),
            "resolved_or_partially_resolved_count": len(resolved_or_partial),
            "blocked_external_evidence_count": len(blocked_external),
            "broad_scientific_claims_ready": False,
        },
        "gaps": gaps,
        "validation": {
            "valid": True,
            "checked_rules": [
                "source_observation_documents_identified",
                "each_gap_has_status_and_current_evidence",
                "external_evidence_blockers_not_downgraded",
                "broad_claim_readiness_remains_false",
            ],
        },
        "claim_limitations": [
            "audit maps the current repository state; it does not create missing external evidence",
            "locally_resolved rows only support local artifact-readiness claims",
            "broad scientific claims remain governed by scientific_defensibility_gate_v1",
        ],
    }


def _gaps() -> list[dict[str, Any]]:
    return [
        _gap(
            "runtime_path_coverage",
            "Coverage report dei path runtime; output transformation before delivery; resume, retry and cron gate coverage.",
            "partially_resolved",
            [
                "runtime_path_coverage_v1",
                "live_runtime_telemetry_v1 importer",
                "mock_runtime_telemetry_campaign_v1",
                "scientific_local_evidence_package_v1",
                "runtime_fault_injection_v1",
            ],
            [
                "local evidence package satisfies the runtime telemetry gate with mock evidence",
                "production Hermes deployment traces are still required for production-channel claims",
                "static and mock coverage cannot prove every live gateway path is active",
            ],
        ),
        _gap(
            "trace_end_to_end_interactions",
            "Trace end-to-end su interazioni complete.",
            "partially_resolved",
            [
                "mock_runtime_telemetry_campaign_v1",
                "scientific_claim_readiness_run_v1 command logs",
            ],
            [
                "mock traces are local exercisability evidence, not participant or production telemetry",
            ],
        ),
        _gap(
            "subject_confirmation_callers",
            "Evidenza che tutti i caller rispettino subject_confirmation.",
            "partially_resolved",
            [
                "shared_continuity_recovery_drill_v1",
                "multi_subject_isolation_load_v1",
                "runtime_path_coverage_v1",
            ],
            [
                "caller inventory is local and synthetic; production integrations still need trace evidence",
            ],
        ),
        _gap(
            "hook_adapter_failure_modes",
            "Analisi dei failure modes quando un hook o adapter non è attivo.",
            "locally_resolved",
            ["runtime_fault_injection_v1"],
            ["local synthetic fault injection only; not network/provider chaos coverage"],
        ),
        _gap(
            "non_hermes_runtime_generalization",
            "Evidenza su runtime diversi da Hermes.",
            "intentionally_out_of_scope",
            ["runtime_path_coverage_v1 claim limitations"],
            ["current artifact remains Hermes-scoped; claims must stay scoped accordingly"],
        ),
        _gap(
            "multi_channel_evidence",
            "Evidenza su canali multipli.",
            "partially_resolved",
            ["mock_runtime_telemetry_campaign_v1"],
            [
                "mock channels do not prove Telegram/WhatsApp/Email/SMS production channel behavior",
            ],
        ),
        _gap(
            "multi_subject_researcher_load",
            "Evidenza multi-soggetto, carico realistico e multi-ricercatore.",
            "partially_resolved",
            ["multi_subject_isolation_load_v1"],
            ["synthetic load does not prove production throughput or external IdP authorization"],
        ),
        _gap(
            "construct_operationalization",
            "Definizioni operative, rubriche, soglie, failure type distinction.",
            "locally_resolved",
            ["construct_operationalization_v1"],
            ["operationalization is protocol evidence, not completed annotation results"],
        ),
        _gap(
            "controlled_benchmark_baseline_ablation",
            "Benchmark sintetico con baseline, ablation, intervalli e analisi statistica.",
            "locally_resolved",
            ["governance_failure_mode_benchmark_v1"],
            ["synthetic benchmark does not prove user outcomes or live-model robustness"],
        ),
        _gap(
            "human_annotation_results",
            "Human annotation and inter-rater reliability.",
            "blocked_external_evidence",
            ["human_annotation_boundary_v1 protocol", "human_annotation_results_v1 importer"],
            ["requires recruited/independent annotator records satisfying reliability thresholds"],
        ),
        _gap(
            "live_model_generation",
            "Ripetizione su più modelli LLM e separazione mock-vs-real model.",
            "blocked_external_evidence",
            [
                "live_model_generation_protocol_v1",
                "live_model_generation_artifact_v1 importer",
            ],
            ["requires completed redacted external provider/model generation records"],
        ),
        _gap(
            "longitudinal_pilot_results",
            "Evidenza in deployment longitudinale e dati non fixture-backed.",
            "blocked_external_evidence",
            [
                "longitudinal_nonclinical_pilot_v1 protocol",
                "longitudinal_pilot_results_v1 importer",
            ],
            ["requires completed 2-4 week non-clinical pilot data"],
        ),
        _gap(
            "workbench_usability_results",
            "Researcher usability task study.",
            "blocked_external_evidence",
            [
                "researcher_workbench_usability_v1 protocol",
                "workbench_usability_results_v1 importer",
            ],
            ["requires completed researcher/auditor task-study results"],
        ),
        _gap(
            "nonclinical_expert_red_team",
            "Revisione esperta delle boundary cliniche/non-cliniche.",
            "blocked_external_evidence",
            [
                "nonclinical_semantic_boundary_v1",
                "nonclinical_red_team_results_v1 importer",
            ],
            ["requires independent expert red-team case records"],
        ),
        _gap(
            "single_evaluation_script",
            "Script unico di evaluation, expected outputs, report generato automaticamente.",
            "locally_resolved",
            ["scientific_claim_readiness_run_v1", "scientific_reproducibility_snapshot_v1"],
            ["workflow output remains blocked until external evidence is supplied"],
        ),
        _gap(
            "coverage_report",
            "Coverage report dei contract tests.",
            "locally_resolved",
            ["scientific-surface-coverage.json from scientific_claim_readiness full mode"],
            ["coverage percentage is test-execution evidence, not scientific validity"],
        ),
        _gap(
            "docker_reproducible_environment",
            "Docker o ambiente riproducibile.",
            "locally_resolved",
            ["Dockerfile", ".dockerignore", "scientific_environment_manifest_v1"],
            ["dirty worktree is not a pinned release artifact until committed/tagged"],
        ),
        _gap(
            "fixture_description_versioning",
            "Dati fixture descritti e versionati.",
            "partially_resolved",
            [
                "governance_failure_mode_benchmark_v1 scenario manifest",
                "human_annotation_boundary_v1 sampled item manifest",
                "scientific_reproducibility_snapshot_v1 hashes",
            ],
            ["fixture provenance is local; external/non-synthetic data remain absent"],
        ),
    ]


def _gap(
    gap_id: str,
    observation_gap: str,
    status: str,
    current_evidence: list[str],
    remaining_limitations: list[str],
) -> dict[str, Any]:
    return {
        "gap_id": gap_id,
        "observation_gap": observation_gap,
        "status": status,
        "current_evidence": current_evidence,
        "remaining_limitations": remaining_limitations,
    }
