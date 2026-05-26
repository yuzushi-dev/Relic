"""relic.eval — Evaluation and replication harness for Relic E2E."""

from relic.eval.ablation import (
    AblationComparison,
    AblationResult,
    AblationStudy,
    compute_ablation_comparison,
)
from relic.eval.baselines import (
    Baseline,
    BaselineMetrics,
    BaselineType,
    compare_baselines,
    create_baseline,
    run_baseline,
    run_baselines,
)
from relic.eval.controlled_benchmark import run_governance_benchmark
from relic.eval.human_annotation import (
    BINARY_LABELS,
    LIKERT_DIMENSIONS,
    build_annotation_packet,
    build_annotation_results_report,
    build_annotation_results_report_from_file,
    compute_binary_agreement,
    compute_likert_icc,
)
from relic.eval.longitudinal_pilot import (
    build_longitudinal_pilot_protocol,
    build_longitudinal_pilot_results_report,
    build_longitudinal_pilot_results_report_from_file,
)
from relic.eval.runtime_path_coverage import build_runtime_path_coverage_report
from relic.eval.chronicle_audit_coverage import build_chronicle_audit_coverage_report
from relic.eval.workbench_usability import (
    build_workbench_usability_protocol,
    build_workbench_usability_results_report,
    build_workbench_usability_results_report_from_file,
)
from relic.eval.shared_continuity_recovery import (
    build_shared_continuity_recovery_drill_report,
)
from relic.eval.multi_subject_isolation_load import (
    build_multi_subject_isolation_load_report,
)
from relic.eval.runtime_fault_injection import build_runtime_fault_injection_report
from relic.eval.construct_operationalization import (
    build_construct_operationalization_report,
)
from relic.eval.nonclinical_semantic_boundary import (
    build_nonclinical_semantic_boundary_report,
    build_nonclinical_red_team_results_report,
    build_nonclinical_red_team_results_report_from_file,
)
from relic.eval.scientific_defensibility import (
    build_scientific_defensibility_report,
    build_scientific_defensibility_report_from_file,
)
from relic.eval.scientific_evidence_bundle import (
    build_scientific_evidence_bundle,
    build_scientific_evidence_bundle_from_file,
)
from relic.eval.scientific_environment_manifest import (
    build_scientific_environment_manifest,
)
from relic.eval.scientific_local_evidence_package import (
    build_scientific_local_evidence_package,
)
from relic.eval.scientific_observation_remediation_audit import (
    build_scientific_observation_remediation_audit,
)
from relic.eval.scientific_reproducibility_snapshot import (
    build_scientific_reproducibility_snapshot,
)
from relic.eval.live_runtime_telemetry import (
    build_live_runtime_telemetry_report,
    build_live_runtime_telemetry_report_from_file,
    run_mock_gateway_telemetry_campaign,
)
from relic.eval.live_model_generation import (
    build_live_model_generation_artifact,
    build_live_model_generation_artifact_from_file,
    build_live_model_generation_protocol,
    run_live_model_generation_trial,
)
from relic.eval.debug_bundle import DebugBundle, RedactedEntry, SyntheticEntry, emit_debug_bundle
from relic.eval.fixtures import (
    EvalScenario,
    FixtureLoader,
    FixtureType,
    ScenarioType,
    load_scenario_from_jsonl,
)
from relic.eval.harness import (
    HARD_THRESHOLDS,
    ReleaseGateHarness,
    ReleaseGateReport,
    ReleaseGateResult,
    ReleaseGateStatus,
    ReleaseGateThreshold,
    evaluate_release_gates,
)
from relic.eval.memory_dynamics import (
    MemoryDynamicsScenarioType,
    MemoryDynamicsScore,
    MemoryDynamicsSuiteResult,
    evaluate_memory_dynamics_suite,
    evaluate_memory_dynamics_task,
    evaluate_memory_update,
    evaluate_memory_correction,
    evaluate_stale_detection,
    evaluate_forgetting_behavior,
    get_memory_dynamics_scores,
)
from relic.eval.memory_positive import (
    MemoryPositiveScenarioType,
    MemoryPositiveTask,
    MemoryPositiveSuiteResult,
    evaluate_memory_positive_suite,
    evaluate_memory_positive_task,
    get_memory_positive_metric_result,
)
from relic.eval.metrics import (
    CorrectionObedienceMetric,
    ForgettingAwareMetric,
    MemoryPositiveMetric,
    MetricResult,
    PrivacyLeakageMetric,
    SeverityLevel,
    SeverityMetrics,
    compute_metrics,
)
from relic.eval.mock_model import MockModel, MockResponse, create_mock_model
from relic.eval.replication_bundle import (
    ReplicationBundle,
    TraceEntry,
    build_bundle,
    create_trace_entry,
    load_bundle,
)
from relic.eval.report import EvalReport, generate_report, save_report
from relic.eval.gumi_roleplay import (
    FalseLivedExperienceType,
    FalseLivedExperienceResult,
    CoerciveAttachmentType,
    CoerciveAttachmentResult,
    PromptContextCompletenessResult,
    RoleplayScenario,
    detect_false_lived_experience,
    detect_coercive_attachment,
    evaluate_prompt_context_completeness,
    evaluate_roleplay_scenario,
    evaluate_roleplay_suite,
    get_false_lived_experience_metric_results,
    get_coercive_attachment_metric_results,
)
from relic.eval.gumi_roleplay_metrics import (
    REQUIRED_FAMILIES,
    RoleplayMetric,
    all_families_present,
)

__all__ = [
    # Ablation
    "AblationComparison",
    "AblationResult",
    "AblationStudy",
    "compute_ablation_comparison",
    # Baselines
    "Baseline",
    "BaselineMetrics",
    "BaselineType",
    "compare_baselines",
    "create_baseline",
    "run_baseline",
    "run_baselines",
    "run_governance_benchmark",
    "BINARY_LABELS",
    "LIKERT_DIMENSIONS",
    "build_annotation_packet",
    "build_annotation_results_report",
    "build_annotation_results_report_from_file",
    "compute_binary_agreement",
    "compute_likert_icc",
    "build_longitudinal_pilot_protocol",
    "build_longitudinal_pilot_results_report",
    "build_longitudinal_pilot_results_report_from_file",
    "build_runtime_path_coverage_report",
    "build_chronicle_audit_coverage_report",
    "build_workbench_usability_protocol",
    "build_workbench_usability_results_report",
    "build_workbench_usability_results_report_from_file",
    "build_shared_continuity_recovery_drill_report",
    "build_multi_subject_isolation_load_report",
    "build_runtime_fault_injection_report",
    "build_construct_operationalization_report",
    "build_nonclinical_semantic_boundary_report",
    "build_nonclinical_red_team_results_report",
    "build_nonclinical_red_team_results_report_from_file",
    "build_scientific_defensibility_report",
    "build_scientific_defensibility_report_from_file",
    "build_scientific_evidence_bundle",
    "build_scientific_evidence_bundle_from_file",
    "build_scientific_environment_manifest",
    "build_scientific_local_evidence_package",
    "build_scientific_observation_remediation_audit",
    "build_scientific_reproducibility_snapshot",
    "build_live_runtime_telemetry_report",
    "build_live_runtime_telemetry_report_from_file",
    "run_mock_gateway_telemetry_campaign",
    "build_live_model_generation_artifact",
    "build_live_model_generation_artifact_from_file",
    "build_live_model_generation_protocol",
    "run_live_model_generation_trial",
    # Debug bundle
    "DebugBundle",
    "RedactedEntry",
    "SyntheticEntry",
    "emit_debug_bundle",
    # Fixtures
    "EvalScenario",
    "FixtureLoader",
    "FixtureType",
    "ScenarioType",
    "load_scenario_from_jsonl",
    # Harness (PR09)
    "HARD_THRESHOLDS",
    "ReleaseGateHarness",
    "ReleaseGateReport",
    "ReleaseGateResult",
    "ReleaseGateStatus",
    "ReleaseGateThreshold",
    "evaluate_release_gates",
    # Memory dynamics (PR09)
    "MemoryDynamicsScenarioType",
    "MemoryDynamicsScore",
    "MemoryDynamicsSuiteResult",
    "evaluate_memory_dynamics_suite",
    "evaluate_memory_dynamics_task",
    "evaluate_memory_update",
    "evaluate_memory_correction",
    "evaluate_stale_detection",
    "evaluate_forgetting_behavior",
    "get_memory_dynamics_scores",
    # Memory positive (PR09)
    "MemoryPositiveScenarioType",
    "MemoryPositiveTask",
    "MemoryPositiveSuiteResult",
    "evaluate_memory_positive_suite",
    "evaluate_memory_positive_task",
    "get_memory_positive_metric_result",
    # Metrics
    "CorrectionObedienceMetric",
    "ForgettingAwareMetric",
    "MemoryPositiveMetric",
    "MetricResult",
    "PrivacyLeakageMetric",
    "SeverityLevel",
    "SeverityMetrics",
    "compute_metrics",
    # Mock model
    "MockModel",
    "MockResponse",
    "create_mock_model",
    # Report
    "EvalReport",
    "generate_report",
    "save_report",
    # Replication bundle
    "ReplicationBundle",
    "TraceEntry",
    "build_bundle",
    "create_trace_entry",
    "load_bundle",
    # Gumi roleplay (PR09)
    "FalseLivedExperienceType",
    "FalseLivedExperienceResult",
    "CoerciveAttachmentType",
    "CoerciveAttachmentResult",
    "PromptContextCompletenessResult",
    "RoleplayScenario",
    "detect_false_lived_experience",
    "detect_coercive_attachment",
    "evaluate_prompt_context_completeness",
    "evaluate_roleplay_scenario",
    "evaluate_roleplay_suite",
    "get_false_lived_experience_metric_results",
    "get_coercive_attachment_metric_results",
    # Gumi roleplay metrics
    "REQUIRED_FAMILIES",
    "RoleplayMetric",
    "all_families_present",
]
