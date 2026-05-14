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
