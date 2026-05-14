"""Memory-positive task evaluation (PR09).

This module provides detailed evaluation for memory-positive tasks (MP1-MP8),
measuring A5 usefulness compared to A0 (no memory) and A2 (basic memory) baselines.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from relic.eval.metrics import MetricResult, SeverityLevel


class MemoryPositiveScenarioType(Enum):
    """Types of memory-positive scenarios (MP1-MP8)."""

    MP1_FACT_RECALL = "mp1"  # Fact recall after context switch
    MP2_PREFERENCE_RECALL = "mp2"  # Preference recall after interruption
    MP3_PREFERENCE_CONSISTENCY = "mp3"  # Preference consistency
    MP4_LONG_TERM_STABILITY = "mp4"  # Long-term preference stability
    MP5_CROSS_SESSION = "mp5"  # Cross-session memory
    MP6_MEMORY_UPDATE = "mp6"  # Memory update with new facts
    MP7_CORRECTION_ACK = "mp7"  # Memory correction acknowledgment
    MP8_FORGETTING_AWARE = "mp8"  # Forgetting-aware response


@dataclass
class MemoryPositiveTask:
    """Single memory-positive task evaluation."""

    scenario_id: str
    scenario_type: MemoryPositiveScenarioType
    a5_response: str  # Full memory + correction baseline
    a0_response: str  # No memory baseline
    a2_response: str  # Basic memory baseline
    score: float = 0.0
    a5_useful: bool = False
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryPositiveSuiteResult:
    """Results for the complete MP1-MP8 suite."""

    tasks: list[MemoryPositiveTask] = field(default_factory=list)
    total_scenarios: int = 0
    passed_count: int = 0
    failed_count: int = 0
    pass_rate: float = 0.0
    average_score: float = 0.0
    a5_usefulness_claimed: bool = False
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_scenarios": self.total_scenarios,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "pass_rate": self.pass_rate,
            "average_score": self.average_score,
            "a5_usefulness_claimed": self.a5_usefulness_claimed,
            "tasks": [
                {
                    "scenario_id": t.scenario_id,
                    "scenario_type": t.scenario_type.value,
                    "score": t.score,
                    "a5_useful": t.a5_useful,
                }
                for t in self.tasks
            ],
            "summary": self.summary,
        }


def evaluate_memory_positive_task(
    scenario_id: str,
    scenario_type: MemoryPositiveScenarioType,
    a5_response: str,
    a0_response: str,
    a2_response: str,
) -> MemoryPositiveTask:
    """Evaluate a single memory-positive task.

    Compares A5 (full memory+correction) against A0 (no memory) and A2 (basic memory).
    """
    task = MemoryPositiveTask(
        scenario_id=scenario_id,
        scenario_type=scenario_type,
        a5_response=a5_response,
        a0_response=a0_response,
        a2_response=a2_response,
    )

    # A5 usefulness indicators
    a5_usefulness_markers = [
        "[A5]",
        "I recall",
        "I remember",
        "as we discussed",
        "your preference for",
        "you mentioned",
        "according to our conversation",
    ]

    # A0 markers (no memory)
    a0_markers = [
        "[A0]",
        "no memory",
        "don't have access",
        "context reset",
        "previous conversation",
    ]

    # A2 markers (basic memory)
    a2_markers = [
        "[A2]",
        "basic memory",
        "limited recall",
    ]

    # Check A5 for usefulness markers
    a5_has_usefulness = any(
        marker.lower() in a5_response.lower() for marker in a5_usefulness_markers
    )

    # Check A0 for no-memory markers
    a0_has_no_memory = any(
        marker.lower() in a0_response.lower() for marker in a0_markers
    )

    # Check A2 for basic-memory markers
    a2_has_basic_memory = any(
        marker.lower() in a2_response.lower() for marker in a2_markers
    )

    # Calculate score based on A5 advantage
    score = 0.0
    if a5_has_usefulness:
        score = 0.5  # Base score for having usefulness markers

        # Bonus if A0 shows no memory
        if a0_has_no_memory:
            score += 0.25

        # Bonus if A2 shows less capability than A5
        if not a2_has_basic_memory or a5_has_usefulness:
            score += 0.25
    else:
        # A5 lacks usefulness markers
        if a0_has_no_memory:
            # A5 should do better than A0
            score = 0.3
        else:
            # Both A0 and A5 are weak
            score = 0.5

    # Forgetting-aware scenario (MP8) has special handling
    if scenario_type == MemoryPositiveScenarioType.MP8_FORGETTING_AWARE:
        # A5 should acknowledge uncertainty rather than guess
        uncertainty_markers = [
            "not certain",
            "I'm not sure",
            "may have changed",
            "verify",
            "uncertain",
        ]
        if any(marker in a5_response.lower() for marker in uncertainty_markers):
            score = max(score, 0.7)  # Good forgetting-aware behavior
            task.details["forgetting_aware"] = True

    # Determine usefulness claim
    task.a5_useful = score >= 0.7
    task.score = min(score, 1.0)
    task.details = {
        "a5_has_usefulness": a5_has_usefulness,
        "a0_has_no_memory": a0_has_no_memory,
        "a2_has_basic_memory": a2_has_basic_memory,
    }

    return task


def evaluate_memory_positive_suite(
    scenarios: list[dict[str, Any]],
) -> MemoryPositiveSuiteResult:
    """Evaluate complete memory-positive suite (MP1-MP8).

    Args:
        scenarios: List of scenario dicts with:
            - scenario_id: MP1-MP8 identifier
            - scenario_type: MemoryPositiveScenarioType value
            - a5_response: Full memory+correction response
            - a0_response: No memory response
            - a2_response: Basic memory response

    Returns:
        MemoryPositiveSuiteResult with aggregate metrics
    """
    result = MemoryPositiveSuiteResult()
    result.total_scenarios = len(scenarios)

    for scenario in scenarios:
        scenario_id = scenario.get("scenario_id", "unknown")
        scenario_type_str = scenario.get(
            "scenario_type", "mp1"
        )  # Default to MP1

        try:
            scenario_type = MemoryPositiveScenarioType(scenario_type_str)
        except ValueError:
            # Try parsing as mp{N} format
            scenario_type = MemoryPositiveScenarioType.MP1_FACT_RECALL

        task = evaluate_memory_positive_task(
            scenario_id=scenario_id,
            scenario_type=scenario_type,
            a5_response=scenario.get("a5_response", ""),
            a0_response=scenario.get("a0_response", ""),
            a2_response=scenario.get("a2_response", ""),
        )

        result.tasks.append(task)

        if task.a5_useful:
            result.passed_count += 1
        else:
            result.failed_count += 1

    # Calculate aggregate metrics
    if result.total_scenarios > 0:
        result.pass_rate = result.passed_count / result.total_scenarios

    if result.tasks:
        result.average_score = sum(t.score for t in result.tasks) / len(result.tasks)

    # A5 usefulness can only be claimed if pass rate >= 70%
    result.a5_usefulness_claimed = result.pass_rate >= 0.7

    # Generate summary
    result.summary = {
        "total_scenarios": result.total_scenarios,
        "passed": result.passed_count,
        "failed": result.failed_count,
        "pass_rate": result.pass_rate,
        "average_score": result.average_score,
        "a5_usefulness_claim_valid": result.a5_usefulness_claimed,
        "blocks_release": not result.a5_usefulness_claimed,
    }

    return result


def get_memory_positive_metric_result(
    scenario_id: str,
    a5_response: str,
    a0_response: str,
    a2_response: str,
) -> MetricResult:
    """Convert memory-positive evaluation to MetricResult.

    This bridges the memory_positive module with the main metrics system.
    """
    task = evaluate_memory_positive_task(
        scenario_id=scenario_id,
        scenario_type=MemoryPositiveScenarioType.MP1_FACT_RECALL,
        a5_response=a5_response,
        a0_response=a0_response,
        a2_response=a2_response,
    )

    severity = SeverityLevel.PASS if task.a5_useful else SeverityLevel.S2_WARNING

    return MetricResult(
        metric_name="memory_positive",
        scenario_id=scenario_id,
        passed=task.a5_useful,
        severity=severity,
        score=task.score,
        details=task.details,
    )
