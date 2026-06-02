"""PR22I, R1–R10 families must all be present in the metric stream."""
from __future__ import annotations

from relic.eval.gumi_roleplay_metrics import (
    REQUIRED_FAMILIES,
    RoleplayMetric,
    all_families_present,
)


def _stub() -> list[RoleplayMetric]:
    return [
        RoleplayMetric(
            scenario_family=f,
            admission_decisions=0,
            correct_admission_rate=1.0,
            disclosure_when_challenged_rate=1.0,
            physical_experience_violations=0,
            dependency_claim_violations=0,
        )
        for f in REQUIRED_FAMILIES
    ]


def test_all_families_present() -> None:
    assert all_families_present(_stub())


def test_missing_family_detected() -> None:
    samples = _stub()[:-1]
    assert all_families_present(samples) is False
