"""Guards the reproducible scientific-defensibility gate states.

These assertions are the CI lock for the README/manuscript claim that the gate is
1/7 by default and 3/7 over the committed local evidence. Without this test the
claim can silently drift (the default CI `make test` profile does not exercise the
eval surface).
"""

from __future__ import annotations

from relic.eval.scientific_defensibility import build_scientific_defensibility_report

from scripts.gate_local_evidence import build_committed_evidence_bundle

_SATISFIED_WITH_COMMITTED_EVIDENCE = {
    "controlled_governance_benchmark",
    "live_model_generation_campaign",
    "live_runtime_telemetry",
}
_BLOCKED_PENDING_HUMAN_DATA = {
    "human_annotation_results",
    "nonclinical_expert_red_team",
    "longitudinal_pilot_results",
    "workbench_usability_results",
}


def _status_by_id(report: dict) -> dict[str, str]:
    return {r["requirement_id"]: r["status"] for r in report["requirements"]}


def test_default_gate_is_one_of_seven():
    report = build_scientific_defensibility_report()
    assert report["summary"]["satisfied_count"] == 1
    assert report["overall_status"] == "blocked"
    statuses = _status_by_id(report)
    assert statuses["controlled_governance_benchmark"] == "satisfied"
    # Everything that needs supplied evidence is blocked without a bundle.
    for requirement_id in _SATISFIED_WITH_COMMITTED_EVIDENCE - {"controlled_governance_benchmark"}:
        assert statuses[requirement_id] == "blocked"


def test_committed_local_evidence_reaches_three_of_seven():
    bundle = build_committed_evidence_bundle()
    report = build_scientific_defensibility_report(evidence_bundle=bundle)
    assert report["summary"]["satisfied_count"] == 3
    assert report["overall_status"] == "blocked"  # 4 human requirements still block
    statuses = _status_by_id(report)
    for requirement_id in _SATISFIED_WITH_COMMITTED_EVIDENCE:
        assert statuses[requirement_id] == "satisfied", requirement_id
    for requirement_id in _BLOCKED_PENDING_HUMAN_DATA:
        assert statuses[requirement_id] == "blocked", requirement_id
