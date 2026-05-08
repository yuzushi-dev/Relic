"""Evaluation fixtures and scenario definitions.

This module defines the evaluation harness fixtures for Relic E2E.
Fixtures are redacted, deterministic, and contain no raw private data.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class FixtureType(Enum):
    """Types of evaluation fixtures."""

    PRIVACY = "privacy"
    CORRECTION = "correction"
    MEMORY_POSITIVE = "memory_positive"
    UPDATE = "update"
    STALE_MEMORY = "stale_memory"
    REPLICATION = "replication"


class ScenarioType(Enum):
    """Scenario categories for evaluation."""

    # Memory-positive scenarios (MP1-MP8)
    MP1 = "mp1"  # Fact recall after context switch
    MP2 = "mp2"  # Preference recall after interruption
    MP3 = "mp3"  # Preference consistency
    MP4 = "mp4"  # Long-term preference stability
    MP5 = "mp5"  # Cross-session memory
    MP6 = "mp6"  # Memory update with new facts
    MP7 = "mp7"  # Memory correction acknowledgment
    MP8 = "mp8"  # Forgetting-aware response
    # Severity scenarios (S0-S2)
    S0_HARD = "s0_hard"  # Hard violation - must block
    S1_QUARANTINE = "s1_quarantine"  # Quarantine required
    S2_WARNING = "s2_warning"  # Warning, log for review
    # Baseline scenarios (A0-A5)
    A0_BASELINE = "a0_baseline"  # No memory, no correction
    A1_NO_MEMORY = "a1_no_memory"  # No memory capability
    A2_BASIC_MEMORY = "a2_basic_memory"  # Basic memory without correction
    A3_CORRECTION = "a3_correction"  # Correction only
    A4_PARTIAL = "a4_partial"  # Partial memory+correction
    A5_FULL = "a5_full"  # Full memory+correction


@dataclass
class EvalScenario:
    """Single evaluation scenario."""

    scenario_id: str
    scenario_type: ScenarioType
    fixture_type: FixtureType
    prompt: str  # Redacted prompt
    expected_response: str  # Redacted expected response
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "scenario_type": self.scenario_type.value,
            "fixture_type": self.fixture_type.value,
            "prompt": self.prompt,
            "expected_response": self.expected_response,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvalScenario":
        return cls(
            scenario_id=data["scenario_id"],
            scenario_type=ScenarioType(data["scenario_type"]),
            fixture_type=FixtureType(data["fixture_type"]),
            prompt=data["prompt"],
            expected_response=data["expected_response"],
            metadata=data.get("metadata", {}),
        )


class FixtureLoader:
    """Loads evaluation fixtures from fixtures directory."""

    def __init__(self, fixtures_dir: Path | None = None):
        if fixtures_dir is None:
            fixtures_dir = Path(__file__).parent.parent.parent / "fixtures"
        self.fixtures_dir = Path(fixtures_dir)

    def load_jsonl(self, fixture_name: str) -> list[EvalScenario]:
        """Load scenarios from a JSONL fixture file."""
        fixture_path = self.fixtures_dir / fixture_name
        if not fixture_path.exists():
            raise FileNotFoundError(f"Fixture not found: {fixture_path}")

        scenarios = []
        with open(fixture_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    import json

                    data = json.loads(line)
                    scenarios.append(EvalScenario.from_dict(data))
        return scenarios

    def load_memory_positive(self) -> list[EvalScenario]:
        """Load memory-positive scenarios (MP1-MP8)."""
        return self.load_jsonl("memory-positive/memory_positive_scenarios.jsonl")

    def list_fixtures(self) -> list[str]:
        """List available fixtures."""
        fixtures = []
        for item in self.fixtures_dir.rglob("*.jsonl"):
            rel_path = item.relative_to(self.fixtures_dir)
            fixtures.append(str(rel_path))
        return sorted(fixtures)


def load_scenario_from_jsonl(jsonl_path: Path | str) -> list[EvalScenario]:
    """Load scenarios from a JSONL file path."""
    loader = FixtureLoader()
    return loader.load_jsonl(str(Path(jsonl_path).relative_to(loader.fixtures_dir)))


# Severity thresholds for evaluation
SEVERITY_THRESHOLDS = {
    "s0_hard_violation": 0,  # Any S0 violation is a hard fail
    "s1_quarantine": 1,  # S1 triggers quarantine
    "s2_warning": 2,  # S2 logs warning
}
