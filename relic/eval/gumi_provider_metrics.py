"""Provider comparison metrics (PR19F)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderMetric:
    provider: str
    candidates_emitted: int
    candidates_admitted: int
    redaction_coverage: float
    relational_truth_claims: int  # must remain 0 for non-runtime providers

    @property
    def admission_rate(self) -> float:
        if self.candidates_emitted == 0:
            return 0.0
        return self.candidates_admitted / self.candidates_emitted


def comparison_table(metrics: list[ProviderMetric]) -> list[dict]:
    return [
        {
            "provider": m.provider,
            "candidates_emitted": m.candidates_emitted,
            "candidates_admitted": m.candidates_admitted,
            "admission_rate": round(m.admission_rate, 4),
            "redaction_coverage": round(m.redaction_coverage, 4),
            "relational_truth_claims": m.relational_truth_claims,
        }
        for m in metrics
    ]
