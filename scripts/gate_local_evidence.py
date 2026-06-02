#!/usr/bin/env python3
"""Reproduce the scientific-defensibility gate over committed local evidence.

The default gate invocation
(`eval_run.py --experiment scientific_defensibility_gate`) passes no evidence
bundle, so only the code-regenerable controlled governance benchmark is counted
and the gate reports 1/7. This script assembles the evidence bundle from the
*committed* live-model generation campaign and mock-gateway runtime telemetry
artifacts and re-runs the same gate, which reaches 3/7
(`controlled_governance_benchmark`, `live_model_generation_campaign`,
`live_runtime_telemetry`). The remaining four requirements
(`human_annotation_results`, `nonclinical_expert_red_team`,
`longitudinal_pilot_results`, `workbench_usability_results`) require recruited
human data and stay blocked by design.

This makes the "3/7" state claimed in README/manuscript reproducible from a clean
checkout via a single committed command, rather than a hand-assembled artifact.

Usage:
    python scripts/gate_local_evidence.py            # print summary, exit 1 if blocked
    python scripts/gate_local_evidence.py --json     # also print full gate JSON
    python scripts/gate_local_evidence.py --write     # (re)write the committed 3/7 artifact
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
EVIDENCE_DIR = REPO_ROOT / "docs" / "research" / "evidence" / "live-model-campaign-2026-05-26"
LIVE_MODEL_ARTIFACT = EVIDENCE_DIR / "artifact.json"
RUNTIME_TELEMETRY_ARTIFACT = EVIDENCE_DIR / "mock-runtime-telemetry.json"
GATE_3OF7_OUTPUT = EVIDENCE_DIR / "defensibility-gate-3of7.json"

sys.path.insert(0, str(REPO_ROOT))


def _load(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_committed_evidence_bundle() -> dict[str, Any]:
    """Assemble the gate evidence bundle from committed campaign artifacts."""
    missing = [p for p in (LIVE_MODEL_ARTIFACT, RUNTIME_TELEMETRY_ARTIFACT) if not p.exists()]
    if missing:
        raise SystemExit(
            "missing committed evidence artifact(s): "
            + ", ".join(str(p.relative_to(REPO_ROOT)) for p in missing)
        )
    return {
        "live_model_generation_artifact": _load(LIVE_MODEL_ARTIFACT),
        "live_runtime_telemetry": _load(RUNTIME_TELEMETRY_ARTIFACT),
    }


EXPECTED_SATISFIED = {
    "controlled_governance_benchmark",
    "live_model_generation_campaign",
    "live_runtime_telemetry",
}


def run(*, write: bool, as_json: bool, strict: bool) -> int:
    from relic.eval.scientific_defensibility import build_scientific_defensibility_report

    # Genuine errors (missing/malformed committed evidence) raise SystemExit here.
    bundle = build_committed_evidence_bundle()
    report = build_scientific_defensibility_report(evidence_bundle=bundle)
    summary = report["summary"]

    if write:
        report_with_provenance = dict(report)
        report_with_provenance["_provenance"] = {
            "regenerated_by": "scripts/gate_local_evidence.py",
            "evidence_inputs": {
                str(LIVE_MODEL_ARTIFACT.relative_to(REPO_ROOT)): _sha256(LIVE_MODEL_ARTIFACT),
                str(RUNTIME_TELEMETRY_ARTIFACT.relative_to(REPO_ROOT)): _sha256(
                    RUNTIME_TELEMETRY_ARTIFACT
                ),
            },
        }
        GATE_3OF7_OUTPUT.write_text(
            json.dumps(report_with_provenance, indent=2) + "\n", encoding="utf-8"
        )
        print(f"wrote {GATE_3OF7_OUTPUT.relative_to(REPO_ROOT)}")

    print(
        f"gate (committed local evidence): {summary['satisfied_count']}/"
        f"{summary['requirement_count']} satisfied, overall {report['overall_status']}"
    )
    for requirement in report["requirements"]:
        print(f"  {requirement['requirement_id']}: {requirement['status']}")

    if as_json:
        print(json.dumps(report, indent=2))

    # The four recruited-human requirements are blocked *by design*; a blocked
    # overall status is therefore the expected, correct outcome here and is NOT a
    # failure. This informational script exits 0 once the gate computed
    # successfully (genuine errors already raised above). Release-gating exit-1
    # semantics live in `eval_run.py --experiment scientific_defensibility_gate`
    # and the CI guard `tests/eval/test_gate_local_evidence.py`.
    if strict:
        actual = {r["requirement_id"] for r in report["requirements"] if r["status"] == "satisfied"}
        if actual != EXPECTED_SATISFIED:
            print(
                f"STRICT FAIL: expected exactly {sorted(EXPECTED_SATISFIED)} satisfied, "
                f"got {sorted(actual)}",
                file=sys.stderr,
            )
            return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="also print the full gate report JSON")
    parser.add_argument(
        "--write",
        action="store_true",
        help="(re)write the committed defensibility-gate-3of7.json artifact",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit non-zero unless exactly the expected 3/7 requirements are satisfied",
    )
    args = parser.parse_args(argv)
    return run(write=args.write, as_json=args.json, strict=args.strict)


if __name__ == "__main__":
    sys.exit(main())
