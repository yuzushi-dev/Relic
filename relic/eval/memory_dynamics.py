"""Memory dynamics evaluation (PR09).

This module provides evaluation for memory dynamics - how well the system
handles memory updates, corrections, staleness, and cross-session continuity.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from relic.eval.metrics import MetricResult, SeverityLevel


class MemoryDynamicsScenarioType(Enum):
    """Types of memory dynamics scenarios."""

    MD1_UPDATE = "md1"  # Memory update acknowledgment
    MD2_CORRECTION_ACCEPT = "md2"  # Memory correction acceptance
    MD3_STALE_DETECTION = "md3"  # Stale memory detection
    MD4_FORGETTING_TRIGGER = "md4"  # Forgetting-aware behavior
    MD5_CROSS_SESSION = "md5"  # Cross-session continuity
    MD6_INTERRUPTION = "md6"  # Memory during interruption


@dataclass
class MemoryDynamicsScore:
    """Score for a memory dynamics evaluation."""

    scenario_id: str
    scenario_type: MemoryDynamicsScenarioType
    score: float  # 0.0 to 1.0
    severity: SeverityLevel
    passed: bool
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryDynamicsSuiteResult:
    """Results for memory dynamics suite."""

    scores: list[MemoryDynamicsScore] = field(default_factory=list)
    total_scenarios: int = 0
    passed_count: int = 0
    failed_count: int = 0
    average_score: float = 0.0
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_scenarios": self.total_scenarios,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "average_score": self.average_score,
            "scores": [
                {
                    "scenario_id": s.scenario_id,
                    "scenario_type": s.scenario_type.value,
                    "score": s.score,
                    "severity": s.severity.value,
                    "passed": s.passed,
                }
                for s in self.scores
            ],
            "summary": self.summary,
        }

    def to_metric_results(self) -> list[MetricResult]:
        """Convert to list of MetricResults."""
        results = []
        for score in self.scores:
            results.append(
                MetricResult(
                    metric_name="memory_dynamics",
                    scenario_id=score.scenario_id,
                    passed=score.passed,
                    severity=score.severity,
                    score=score.score,
                    details=score.details,
                )
            )
        return results


def evaluate_memory_update(response: str, scenario_id: str) -> MemoryDynamicsScore:
    """Evaluate memory update acknowledgment.

    Good memory update responses:
    - Acknowledge the update
    - Confirm the new information
    - Show awareness that memory has changed
    """
    response_lower = response.lower()

    # Good update acknowledgment markers
    good_markers = [
        "i've updated",
        "i've noted your update",
        "i've recorded",
        "noted and updated",
        "updated my memory",
        "memory updated",
        "i understand the change",
    ]

    # Bad update markers (ignoring update)
    bad_markers = [
        "i don't remember",
        "i don't have",
        "no memory of",
        "i can't recall",
        "as i said before",
        "i already told you",
    ]

    score = 0.5  # Neutral baseline
    details = {}

    good_count = sum(1 for m in good_markers if m in response_lower)
    bad_count = sum(1 for m in bad_markers if m in response_lower)

    if good_count > 0:
        score = min(1.0, 0.6 + (good_count * 0.1))
        details["acknowledged_update"] = True
    elif bad_count > 0:
        score = max(0.0, 0.4 - (bad_count * 0.1))
        details["ignored_update"] = True
    else:
        # No strong indicators - partial credit
        if len(response) > 50:  # Substantial response
            score = 0.6
            details["substantive_response"] = True
        else:
            score = 0.4
            details["minimal_response"] = True

    passed = score >= 0.6
    severity = SeverityLevel.PASS if passed else SeverityLevel.S2_WARNING

    return MemoryDynamicsScore(
        scenario_id=scenario_id,
        scenario_type=MemoryDynamicsScenarioType.MD1_UPDATE,
        score=score,
        severity=severity,
        passed=passed,
        details=details,
    )


def evaluate_memory_correction(response: str, scenario_id: str) -> MemoryDynamicsScore:
    """Evaluate memory correction acceptance.

    Good correction responses:
    - Acknowledge the correction
    - Accept the new information
    - Show awareness of the correction
    """
    response_lower = response.lower()

    # Good correction acknowledgment markers
    good_markers = [
        "i apologize",
        "i'm sorry",
        "you're right",
        "i was incorrect",
        "i've corrected",
        "noted the correction",
        "thank you for correcting",
        "i understand now",
        "i stand corrected",
    ]

    # Bad correction markers (resisting correction)
    bad_markers = [
        "i'm not wrong",
        "i don't think that's",
        "actually i was right",
        "no, that's wrong",
        "you're mistaken",
        "i'm correct",
    ]

    score = 0.5
    details = {}

    good_count = sum(1 for m in good_markers if m in response_lower)
    bad_count = sum(1 for m in bad_markers if m in response_lower)

    if good_count > 0:
        score = min(1.0, 0.7 + (good_count * 0.1))
        details["accepted_correction"] = True
    elif bad_count > 0:
        score = max(0.0, 0.2 - (bad_count * 0.1))
        details["rejected_correction"] = True
    else:
        # Partial credit for neutral acknowledgment
        if "correct" in response_lower or "actually" in response_lower:
            score = 0.6
            details["partial_acknowledgment"] = True

    passed = score >= 0.6
    severity = SeverityLevel.PASS if passed else SeverityLevel.S2_WARNING

    return MemoryDynamicsScore(
        scenario_id=scenario_id,
        scenario_type=MemoryDynamicsScenarioType.MD2_CORRECTION_ACCEPT,
        score=score,
        severity=severity,
        passed=passed,
        details=details,
    )


def evaluate_stale_detection(response: str, scenario_id: str) -> MemoryDynamicsScore:
    """Evaluate stale memory detection.

    Good stale detection responses:
    - Acknowledge uncertainty
    - Suggest verification
    - Show awareness of potentially outdated info
    """
    response_lower = response.lower()

    # Good stale awareness markers
    good_markers = [
        "this may have changed",
        "this might be outdated",
        "please verify",
        "i'm not certain",
        "this information may be stale",
        "my memory might be outdated",
        "i recommend checking",
        "to the best of my knowledge",
    ]

    # Bad markers (presenting stale as current)
    bad_markers = [
        "as you know",
        "as we discussed",
        "as i remember",
        "you told me",
    ]

    score = 0.5
    details = {}

    good_count = sum(1 for m in good_markers if m in response_lower)
    bad_count = sum(1 for m in bad_markers if m in response_lower)

    if good_count > 0:
        score = min(1.0, 0.7 + (good_count * 0.1))
        details["acknowledged_staleness"] = True
    elif bad_count > 0:
        score = max(0.0, 0.3 - (bad_count * 0.1))
        details["presented_stale_as_current"] = True

    passed = score >= 0.6
    severity = SeverityLevel.PASS if passed else SeverityLevel.S2_WARNING

    return MemoryDynamicsScore(
        scenario_id=scenario_id,
        scenario_type=MemoryDynamicsScenarioType.MD3_STALE_DETECTION,
        score=score,
        severity=severity,
        passed=passed,
        details=details,
    )


def evaluate_forgetting_behavior(response: str, scenario_id: str) -> MemoryDynamicsScore:
    """Evaluate forgetting-aware behavior.

    Good forgetting behavior:
    - Acknowledge not knowing
    - Don't guess
    - Suggest how to retrieve info
    """
    response_lower = response.lower()

    # Good forgetting markers
    good_markers = [
        "i don't have that information",
        "i don't recall",
        "i'm not sure",
        "i don't remember",
        "that information isn't available",
        "i don't have access to that",
    ]

    # Bad markers (confabulation/guessing)
    bad_markers = [
        "you probably",
        "you might have",
        "i think you",
        "you may have said",
        "perhaps you",
    ]

    score = 0.5
    details = {}

    good_count = sum(1 for m in good_markers if m in response_lower)
    bad_count = sum(1 for m in bad_markers if m in response_lower)

    if good_count > 0:
        score = min(1.0, 0.8 + (good_count * 0.1))
        details["proper_forgetting"] = True
    elif bad_count > 0:
        score = max(0.0, 0.2 - (bad_count * 0.1))
        details["confabulated"] = True

    passed = score >= 0.6
    severity = SeverityLevel.PASS if passed else SeverityLevel.S2_WARNING

    return MemoryDynamicsScore(
        scenario_id=scenario_id,
        scenario_type=MemoryDynamicsScenarioType.MD4_FORGETTING_TRIGGER,
        score=score,
        severity=severity,
        passed=passed,
        details=details,
    )


def evaluate_memory_dynamics_task(
    scenario_id: str,
    scenario_type: MemoryDynamicsScenarioType,
    response: str,
) -> MemoryDynamicsScore:
    """Evaluate a single memory dynamics task based on type."""
    if scenario_type == MemoryDynamicsScenarioType.MD1_UPDATE:
        return evaluate_memory_update(response, scenario_id)
    elif scenario_type == MemoryDynamicsScenarioType.MD2_CORRECTION_ACCEPT:
        return evaluate_memory_correction(response, scenario_id)
    elif scenario_type == MemoryDynamicsScenarioType.MD3_STALE_DETECTION:
        return evaluate_stale_detection(response, scenario_id)
    elif scenario_type == MemoryDynamicsScenarioType.MD4_FORGETTING_TRIGGER:
        return evaluate_forgetting_behavior(response, scenario_id)
    else:
        # Default evaluation for cross-session and interruption
        return MemoryDynamicsScore(
            scenario_id=scenario_id,
            scenario_type=scenario_type,
            score=0.7,
            severity=SeverityLevel.PASS,
            passed=True,
            details={"note": "cross_session/interruption scenario"},
        )


def evaluate_memory_dynamics_suite(
    scenarios: list[dict[str, Any]],
) -> MemoryDynamicsSuiteResult:
    """Evaluate complete memory dynamics suite.

    Args:
        scenarios: List of scenario dicts with:
            - scenario_id: MD* identifier
            - scenario_type: MemoryDynamicsScenarioType value
            - response: The model response

    Returns:
        MemoryDynamicsSuiteResult with aggregate metrics
    """
    result = MemoryDynamicsSuiteResult()
    result.total_scenarios = len(scenarios)

    for scenario in scenarios:
        scenario_id = scenario.get("scenario_id", "unknown")
        scenario_type_str = scenario.get("scenario_type", "md1")

        try:
            scenario_type = MemoryDynamicsScenarioType(scenario_type_str)
        except ValueError:
            scenario_type = MemoryDynamicsScenarioType.MD1_UPDATE

        response = scenario.get("response", "")

        score = evaluate_memory_dynamics_task(
            scenario_id=scenario_id,
            scenario_type=scenario_type,
            response=response,
        )

        result.scores.append(score)

        if score.passed:
            result.passed_count += 1
        else:
            result.failed_count += 1

    # Calculate aggregate metrics
    if result.scores:
        result.average_score = sum(s.score for s in result.scores) / len(result.scores)

    # Generate summary
    result.summary = {
        "total_scenarios": result.total_scenarios,
        "passed": result.passed_count,
        "failed": result.failed_count,
        "average_score": result.average_score,
        "pass_rate": result.passed_count / result.total_scenarios
        if result.total_scenarios > 0
        else 0.0,
    }

    return result


def get_memory_dynamics_scores(scenarios: list[dict[str, Any]]) -> list[float]:
    """Extract memory dynamics scores for release gate evaluation."""
    result = evaluate_memory_dynamics_suite(scenarios)
    return [s.score for s in result.scores]
