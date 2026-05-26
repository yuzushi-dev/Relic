"""Local-only scientific evidence package for claim-readiness accounting."""

from __future__ import annotations

from typing import Any

from relic.eval.controlled_benchmark import run_governance_benchmark
from relic.eval.live_runtime_telemetry import run_mock_gateway_telemetry_campaign
from relic.eval.scientific_defensibility import build_scientific_defensibility_report


REPORT_ID = "scientific_local_evidence_package_v1"
CLAIM_SCOPE = "local_synthetic_evidence_package"
REVIEW_DATE = "2026-05-25"


def build_scientific_local_evidence_package() -> dict[str, Any]:
    """Build the maximum local evidence package without external human/provider data."""
    governance = run_governance_benchmark()
    mock_runtime = run_mock_gateway_telemetry_campaign()
    evidence_bundle = {
        "governance_benchmark": governance,
        "live_runtime_telemetry": mock_runtime,
    }
    gate_report = build_scientific_defensibility_report(evidence_bundle=evidence_bundle)
    summary = gate_report["summary"]
    return {
        "report_id": REPORT_ID,
        "claim_scope": CLAIM_SCOPE,
        "methodology": {
            "evidence_model": "local_synthetic_artifact_package_plus_claim_gate",
            "review_date": REVIEW_DATE,
            "provenance_basis": [
                "governance_failure_mode_benchmark_v1",
                "mock_runtime_telemetry_campaign_v1",
                "scientific_defensibility_gate_v1",
            ],
        },
        "summary": {
            "local_evidence_artifact_count": 2,
            "gate_satisfied_count": summary["satisfied_count"],
            "gate_blocked_count": summary["blocked_count"],
            "blocks_scientific_claims": summary["blocks_scientific_claims"],
        },
        "evidence_bundle": evidence_bundle,
        "gate_report": gate_report,
        "validation": {
            "valid": True,
            "checked_rules": [
                "controlled_governance_benchmark_included",
                "mock_runtime_telemetry_included",
                "scientific_defensibility_gate_executed",
                "external_evidence_not_fabricated",
            ],
        },
        "claim_limitations": [
            "local package includes only synthetic/local evidence",
            "mock runtime telemetry is not production telemetry",
            "live provider generations, human annotation, expert red-team, pilot, and Workbench usability evidence remain absent",
        ],
    }
