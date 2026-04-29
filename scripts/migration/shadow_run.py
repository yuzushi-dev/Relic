#!/usr/bin/env python3
"""Export canonical/shadow artifact sets and run the shadow comparison."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an offline OpenClaw vs Hermes shadow comparison.")
    parser.add_argument("--openclaw-data-dir", required=True, help="Canonical OpenClaw RELIC_DATA_DIR")
    parser.add_argument("--hermes-data-dir", required=True, help="Hermes shadow RELIC_DATA_DIR")
    parser.add_argument("--out-dir", required=True, help="Directory where exports and comparison report should be written")
    parser.add_argument("--golden-dir", required=True, help="Golden regression corpus directory")
    parser.add_argument("--run-id", required=True, help="Stable identifier for this shadow run")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    out_dir = Path(args.out_dir)
    openclaw_out = out_dir / "openclaw"
    hermes_out = out_dir / "hermes"
    out_dir.mkdir(parents=True, exist_ok=True)

    steps = [
        [
            sys.executable,
            str(repo_root / "scripts" / "export_shadow_artifacts.py"),
            "--data-dir",
            str(Path(args.openclaw_data_dir)),
            "--out-dir",
            str(openclaw_out),
        ],
        [
            sys.executable,
            str(repo_root / "scripts" / "export_shadow_artifacts.py"),
            "--data-dir",
            str(Path(args.hermes_data_dir)),
            "--out-dir",
            str(hermes_out),
        ],
        [
            sys.executable,
            str(repo_root / "scripts" / "migration" / "shadow_compare.py"),
            "--openclaw-dir",
            str(openclaw_out),
            "--hermes-dir",
            str(hermes_out),
            "--out-dir",
            str(out_dir),
            "--golden-dir",
            str(Path(args.golden_dir)),
            "--run-id",
            str(args.run_id),
        ],
    ]

    for cmd in steps:
        result = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            sys.stderr.write(result.stderr or result.stdout)
            return result.returncode

    print(f"shadow run completed: {args.run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
