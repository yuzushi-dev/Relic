"""PR09-T09b — quarantine_rate, warning_rate, defer_rate must appear in eval report."""
from __future__ import annotations

import pytest
from relic.eval.metrics import MetricResult, SeverityLevel, SeverityMetrics


def _make_result(severity: SeverityLevel, scenario_id: str = "s1") -> MetricResult:
    return MetricResult(
        metric_name="test_metric",
        scenario_id=scenario_id,
        passed=severity == SeverityLevel.PASS,
        severity=severity,
        score=1.0 if severity == SeverityLevel.PASS else 0.0,
    )


def test_summary_contains_quarantine_rate() -> None:
    sm = SeverityMetrics()
    sm.add_result(_make_result(SeverityLevel.S1_QUARANTINE))
    sm.add_result(_make_result(SeverityLevel.PASS))
    summary = sm.get_summary()
    assert "quarantine_rate" in summary
    assert summary["quarantine_rate"] == pytest.approx(0.5)


def test_summary_contains_warning_rate() -> None:
    sm = SeverityMetrics()
    sm.add_result(_make_result(SeverityLevel.S2_WARNING))
    sm.add_result(_make_result(SeverityLevel.PASS))
    summary = sm.get_summary()
    assert "warning_rate" in summary
    assert summary["warning_rate"] == pytest.approx(0.5)


def test_summary_contains_defer_rate() -> None:
    sm = SeverityMetrics()
    sm.add_result(_make_result(SeverityLevel.S1_QUARANTINE))
    sm.add_result(_make_result(SeverityLevel.PASS))
    summary = sm.get_summary()
    assert "defer_rate" in summary


def test_s1_item_with_runtime_influence_would_fail_gate() -> None:
    """S1 items must not reach runtime influence — gate must catch them."""
    sm = SeverityMetrics()
    sm.add_result(_make_result(SeverityLevel.S1_QUARANTINE, "dangerous-s1"))
    summary = sm.get_summary()
    # Any quarantine item means defer_rate > 0 — release gate must block on this
    assert summary["defer_rate"] > 0.0


def test_zero_rates_when_all_pass() -> None:
    sm = SeverityMetrics()
    sm.add_result(_make_result(SeverityLevel.PASS))
    summary = sm.get_summary()
    assert summary["quarantine_rate"] == 0.0
    assert summary["warning_rate"] == 0.0
    assert summary["defer_rate"] == 0.0


def test_rates_not_hidden_in_aggregate() -> None:
    """Rates must be top-level keys, not buried inside nested structures."""
    sm = SeverityMetrics()
    sm.add_result(_make_result(SeverityLevel.S2_WARNING))
    summary = sm.get_summary()
    # All three must be top-level, not hidden in sub-dicts
    for key in ("quarantine_rate", "warning_rate", "defer_rate"):
        assert key in summary, f"'{key}' missing from summary top level"
