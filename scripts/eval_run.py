#!/usr/bin/env python3
"""hermes relic eval-run — Run release gate evaluation and exit(1) on failure.

Usage:
    python scripts/eval_run.py [--json]

Exit codes:
    0  All hard thresholds pass
    1  One or more hard thresholds violated (blocks release)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

from relic.eval.harness import evaluate_release_gates, ReleaseGateStatus


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Relic release gate evaluation")
    parser.add_argument("--json", action="store_true", help="Output JSON report")
    args = parser.parse_args(argv)

    report = evaluate_release_gates()

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(f"Release gate: {report.overall_status.value.upper()}")
        for gate_name, result in report.gate_results.items():
            status = "PASS" if result.passed else "FAIL"
            print(f"  [{status}] {gate_name}: score={result.score:.3f}")
        if report.blocked_gates:
            print(f"\nBLOCKED: {', '.join(report.blocked_gates)}")
        if report.quarantine_gates:
            print(f"QUARANTINE: {', '.join(report.quarantine_gates)}")

    if report.overall_status == ReleaseGateStatus.BLOCKED:
        print("\nRELEASE BLOCKED — hard threshold violated", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
