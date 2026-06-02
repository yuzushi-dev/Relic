"""PR19F, comparison report computes admission rate."""
from __future__ import annotations

from relic.eval.gumi_provider_metrics import ProviderMetric, comparison_table


def test_admission_rate_correct() -> None:
    m = ProviderMetric(
        provider="x",
        candidates_emitted=10,
        candidates_admitted=4,
        redaction_coverage=1.0,
        relational_truth_claims=0,
    )
    assert abs(m.admission_rate - 0.4) < 1e-9


def test_table_serializable() -> None:
    rows = comparison_table(
        [
            ProviderMetric(
                provider="x",
                candidates_emitted=0,
                candidates_admitted=0,
                redaction_coverage=1.0,
                relational_truth_claims=0,
            )
        ]
    )
    assert rows[0]["provider"] == "x"
    assert rows[0]["relational_truth_claims"] == 0
