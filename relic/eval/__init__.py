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

__all__ = [
    "AblationComparison",
    "AblationResult",
    "AblationStudy",
    "compute_ablation_comparison",
    "Baseline",
    "BaselineMetrics",
    "BaselineType",
    "compare_baselines",
    "create_baseline",
    "run_baseline",
    "run_baselines",
    "DebugBundle",
    "RedactedEntry",
    "SyntheticEntry",
    "emit_debug_bundle",
    "EvalScenario",
    "FixtureLoader",
    "FixtureType",
    "ScenarioType",
    "load_scenario_from_jsonl",
    "CorrectionObedienceMetric",
    "ForgettingAwareMetric",
    "MemoryPositiveMetric",
    "MetricResult",
    "PrivacyLeakageMetric",
    "SeverityLevel",
    "SeverityMetrics",
    "compute_metrics",
    "MockModel",
    "MockResponse",
    "create_mock_model",
    "EvalReport",
    "generate_report",
    "save_report",
    "ReplicationBundle",
    "TraceEntry",
    "build_bundle",
    "create_trace_entry",
    "load_bundle",
]
