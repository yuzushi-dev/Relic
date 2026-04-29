"""Reproducibility check for the whitepaper §9 evaluation.

The original figures rely on a private deployment, but the architecture
claim in §9.2 ('longitudinal representation growth') is reproducible on
any deployment DB. This test pins the script interface: given any valid
relic DB, the script produces ``metrics.json`` with the headline
fields the paper reports on (coverage, avg confidence, cumulative
observations, source composition).
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "reproduce_evaluation.py"
DEMO_DB = ROOT / "src" / "mnemon" / "relic.db"


def test_script_file_exists() -> None:
    assert SCRIPT.is_file(), (
        f"expected reproducibility script at {SCRIPT.relative_to(ROOT)}"
    )


def test_script_runs_on_demo_db(tmp_path: Path) -> None:
    assert DEMO_DB.is_file(), "demo DB missing - cannot run smoke test"

    out_dir = tmp_path / "out"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--db", str(DEMO_DB), "--out", str(out_dir)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"script failed: stdout={result.stdout!r} stderr={result.stderr!r}"
    )

    metrics_path = out_dir / "metrics.json"
    assert metrics_path.is_file(), "metrics.json not produced"

    data = json.loads(metrics_path.read_text(encoding="utf-8"))
    for key in ("convergence", "sources", "schema"):
        assert key in data, f"metrics.json missing top-level key {key!r}"

    conv = data["convergence"]
    for key in ("daily_series", "final_coverage_pct", "final_avg_confidence",
                "cumulative_observations"):
        assert key in conv, f"convergence missing {key!r}"

    src = data["sources"]
    assert "by_type" in src and isinstance(src["by_type"], dict)
    assert "total" in src


def test_script_accepts_help_flag() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "--db" in result.stdout
    assert "--out" in result.stdout
