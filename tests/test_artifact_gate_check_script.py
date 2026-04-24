"""Smoke tests for scripts/artifact_gate_check.py.

The script is a Layer 4 watchdog run weekly as `relic:artifact-gate-check`.
It must return 0 and "ok" against the repo's own gate, and return non-zero
when the whitelist drifts.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "artifact_gate_check.py"
GATE = ROOT / "hooks" / "shared" / "artifact-gate.ts"


def test_gate_check_ok_on_repo(tmp_path: Path) -> None:
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, f"expected ok; stderr={r.stderr!r}"
    data = json.loads(r.stdout)
    assert data["status"] == "ok"
    assert data["observed"] == ["PORTRAIT.md"]


def test_gate_check_detects_drift(tmp_path: Path) -> None:
    bogus = tmp_path / "artifact-gate.ts"
    bogus.write_text(
        "export const INJECTABLE_ARTIFACTS = [\"PORTRAIT.md\", \"PROFILE.md\"];\n",
        encoding="utf-8",
    )
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--gate-path", str(bogus), "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 1, f"expected drift exit; got {r.returncode}"
    data = json.loads(r.stderr)
    assert data["status"] == "drift"
    assert "PROFILE.md" in data["added"]


def test_gate_check_handles_missing_file(tmp_path: Path) -> None:
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--gate-path", str(tmp_path / "nope.ts")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 2
