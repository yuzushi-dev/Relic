#!/usr/bin/env python3
"""Layer 4 artifact-gate runtime watchdog.

ADR 001 established that `hooks/shared/artifact-gate.ts` must contain
only ['PORTRAIT.md'] in INJECTABLE_ARTIFACTS. The source-level tests in
tests/test_artifact_gate.py pin this at development time; this script
re-checks the invariant at runtime against whatever tree the live
OpenClaw hooks are loaded from.

Exits non-zero (with a structured message) if the whitelist drifted.
Intended to run weekly as cron `relic:artifact-gate-check`.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

EXPECTED = ["PORTRAIT.md"]


def default_gate_path() -> Path:
    env = os.environ.get("RELIC_ARTIFACT_GATE_PATH")
    if env:
        return Path(env)
    # Try repo-relative layout first.
    repo_guess = Path(__file__).resolve().parents[1] / "hooks" / "shared" / "artifact-gate.ts"
    return repo_guess


def parse_whitelist(src: str) -> list[str]:
    match = re.search(r"INJECTABLE_ARTIFACTS\s*(?::[^=]+)?=\s*\[([^\]]+)\]", src)
    if not match:
        raise RuntimeError("INJECTABLE_ARTIFACTS array not found")
    return re.findall(r"[\"']([^\"']+)[\"']", match.group(1))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gate-path", type=Path, default=None,
                        help="Path to artifact-gate.ts (defaults to repo layout)")
    parser.add_argument("--json", action="store_true",
                        help="Emit a JSON status object on stdout")
    args = parser.parse_args()

    path = args.gate_path or default_gate_path()
    result: dict[str, object] = {
        "gate_path": str(path),
        "expected": EXPECTED,
    }

    if not path.is_file():
        result["status"] = "missing"
        result["error"] = f"gate file not found at {path}"
        print(json.dumps(result) if args.json else f"ERROR: {result['error']}",
              file=sys.stderr)
        return 2

    try:
        items = parse_whitelist(path.read_text(encoding="utf-8"))
    except Exception as exc:
        result["status"] = "parse_error"
        result["error"] = str(exc)
        print(json.dumps(result) if args.json else f"ERROR: {exc}", file=sys.stderr)
        return 3

    result["observed"] = items

    if items == EXPECTED:
        result["status"] = "ok"
        if args.json:
            print(json.dumps(result))
        else:
            print(f"OK: whitelist matches {EXPECTED}")
        return 0

    result["status"] = "drift"
    added = [x for x in items if x not in EXPECTED]
    removed = [x for x in EXPECTED if x not in items]
    result["added"] = added
    result["removed"] = removed
    msg = (
        f"DRIFT: whitelist diverged from {EXPECTED}. "
        f"Added={added} Removed={removed}. "
        f"Update ADR 001 and the companion test, or revert the gate."
    )
    print(json.dumps(result) if args.json else msg, file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
