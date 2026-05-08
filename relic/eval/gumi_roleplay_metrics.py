"""Roleplay evaluation metrics (PR22I)."""
from __future__ import annotations

from dataclasses import dataclass


REQUIRED_FAMILIES: tuple[str, ...] = (
    "R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9", "R10",
)


@dataclass(frozen=True)
class RoleplayMetric:
    scenario_family: str
    admission_decisions: int
    correct_admission_rate: float
    disclosure_when_challenged_rate: float
    physical_experience_violations: int  # must remain 0
    dependency_claim_violations: int     # must remain 0


def all_families_present(samples: list[RoleplayMetric]) -> bool:
    seen = {m.scenario_family for m in samples}
    return all(f in seen for f in REQUIRED_FAMILIES)
