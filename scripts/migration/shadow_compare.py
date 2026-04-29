#!/usr/bin/env python3
"""Compare canonical artifacts against Hermes shadow artifacts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _observation_map(rows: list[dict[str, Any]], identity_fields: list[str]) -> dict[tuple[str, ...], dict[str, Any]]:
    mapped: dict[tuple[str, ...], dict[str, Any]] = {}
    for row in rows:
        identity = tuple(str(row.get(field, "")) for field in identity_fields)
        mapped[identity] = row
    return mapped


def _observations_equivalent(canonical_row: dict[str, Any], hermes_row: dict[str, Any]) -> bool:
    return str(canonical_row.get("extracted_signal", "")) == str(hermes_row.get("extracted_signal", ""))


def _compare_observations(
    canonical_rows: list[dict[str, Any]],
    hermes_rows: list[dict[str, Any]],
    *,
    identity_fields: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    canonical_map = _observation_map(canonical_rows, identity_fields)
    hermes_map = _observation_map(hermes_rows, identity_fields)

    missing: list[dict[str, Any]] = []
    unexpected: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []

    for identity, row in canonical_map.items():
        shadow = hermes_map.get(identity)
        if shadow is None:
            missing.append({"identity": list(identity), "canonical": row})
            continue
        if not _observations_equivalent(row, shadow):
            mismatches.append(
                {
                    "identity": list(identity),
                    "canonical": row,
                    "hermes": shadow,
                }
            )

    for identity, row in hermes_map.items():
        if identity not in canonical_map:
            unexpected.append({"identity": list(identity), "hermes": row})

    return missing, unexpected, mismatches


def _compare_traits(canonical_traits: dict[str, Any], hermes_traits: dict[str, Any]) -> list[dict[str, Any]]:
    diffs: list[dict[str, Any]] = []
    all_keys = sorted(set(canonical_traits) | set(hermes_traits))
    for key in all_keys:
        left = canonical_traits.get(key)
        right = hermes_traits.get(key)
        if left != right:
            diffs.append({"trait_id": key, "canonical": left, "hermes": right})
    return diffs


def _artifact_gate_status(golden_dir: Path, repo_root: Path) -> dict[str, Any]:
    expected = _load_json(golden_dir / "artifact_gate.expected.json")
    gate_src = (repo_root / "hooks" / "shared" / "artifact-gate.ts").read_text(encoding="utf-8")
    match = re.search(r"INJECTABLE_ARTIFACTS\s*(?::[^=]+)?=\s*\[([^\]]+)\]", gate_src)
    if not match:
        return {"status": "fail", "reason": "could not parse runtime artifact gate whitelist"}
    whitelist = re.findall(r"[\"']([^\"']+)[\"']", match.group(1))
    missing_allowed = [name for name in expected["injectable_artifacts"] if name not in whitelist]
    forbidden_present = [name for name in expected["forbidden_artifacts"] if name in whitelist]
    if missing_allowed or forbidden_present:
        return {
            "status": "fail",
            "missing_allowed": missing_allowed,
            "forbidden_present": forbidden_present,
        }
    return {"status": "pass", "whitelist": whitelist}


def build_report(
    *,
    run_id: str,
    canonical_dir: Path,
    hermes_dir: Path,
    golden_dir: Path,
    repo_root: Path,
) -> dict[str, Any]:
    manifest = _load_json(golden_dir / "run_manifest.expected.json")
    identity_fields = list(manifest["observation_match_rule"]["identity_fields"])

    canonical_observations = _load_jsonl(canonical_dir / "observations.jsonl")
    hermes_observations = _load_jsonl(hermes_dir / "observations.jsonl")
    missing, unexpected, mismatches = _compare_observations(
        canonical_observations,
        hermes_observations,
        identity_fields=identity_fields,
    )

    canonical_traits = _load_json(canonical_dir / "traits.json")
    hermes_traits = _load_json(hermes_dir / "traits.json")
    trait_differences = _compare_traits(canonical_traits, hermes_traits)

    canonical_portrait = (canonical_dir / "PORTRAIT.md").read_text(encoding="utf-8")
    hermes_portrait = (hermes_dir / "PORTRAIT.md").read_text(encoding="utf-8")
    portrait_status = {
        "status": "match" if canonical_portrait == hermes_portrait else "mismatch",
        "canonical_path": str(canonical_dir / "PORTRAIT.md"),
        "hermes_path": str(hermes_dir / "PORTRAIT.md"),
    }

    artifact_gate_status = _artifact_gate_status(golden_dir, repo_root)
    rollback_required = bool(
        missing
        or unexpected
        or mismatches
        or trait_differences
        or portrait_status["status"] != "match"
        or artifact_gate_status["status"] != "pass"
    )

    return {
        "run_id": run_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "canonical_runtime": "canonical",
        "shadow_runtime": "hermes",
        "session_source": "hermes",
        "observation_match_rule": manifest["observation_match_rule"],
        "observation_counts": {
            "canonical": len(canonical_observations),
            "hermes": len(hermes_observations),
            "mismatch_count": len(mismatches),
        },
        "missing_from_shadow": missing,
        "unexpected_in_shadow": unexpected,
        "observation_mismatches": mismatches,
        "trait_differences": trait_differences,
        "portrait_status": portrait_status,
        "artifact_gate_status": artifact_gate_status,
        "rollback_required": rollback_required,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare canonical artifacts against Hermes shadow artifacts.")
    parser.add_argument("--canonical-dir", required=True, help="Directory containing canonical artifacts")
    parser.add_argument("--hermes-dir", required=True, help="Directory containing Hermes shadow artifacts")
    parser.add_argument("--out-dir", required=True, help="Directory where comparison artifacts should be written")
    parser.add_argument("--golden-dir", required=True, help="Golden regression corpus directory")
    parser.add_argument("--run-id", required=True, help="Stable identifier for this shadow comparison run")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    report = build_report(
        run_id=args.run_id,
        canonical_dir=Path(args.canonical_dir),
        hermes_dir=Path(args.hermes_dir),
        golden_dir=Path(args.golden_dir),
        repo_root=repo_root,
    )
    (out_dir / "shadow_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    if report["rollback_required"]:
        print(f"shadow comparison failed for {args.run_id}")
        return 1

    print(f"shadow comparison passed for {args.run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
