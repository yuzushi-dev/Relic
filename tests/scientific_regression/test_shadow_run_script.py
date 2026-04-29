from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "shadow_run.py"
GOLDEN = ROOT / "datasets" / "regression" / "golden_v1"


def _seed_data_dir(base_dir: Path, *, signal: str, trait_score: float, portrait: str) -> None:
    base_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(base_dir / "relic.db")
    try:
        conn.execute(
            "CREATE TABLE observations (id INTEGER PRIMARY KEY AUTOINCREMENT, facet_id TEXT NOT NULL, source_type TEXT NOT NULL, source_ref TEXT, content TEXT NOT NULL, extracted_signal TEXT, signal_strength REAL DEFAULT 0.5, signal_position REAL, context TEXT, context_metadata TEXT, created_at TEXT NOT NULL)"
        )
        conn.execute(
            "CREATE TABLE traits (facet_id TEXT PRIMARY KEY, value_position REAL, confidence REAL DEFAULT 0.0, observation_count INTEGER DEFAULT 0, last_observation_at TEXT, last_synthesis_at TEXT, notes TEXT, status TEXT DEFAULT 'insufficient_data')"
        )
        conn.execute(
            "INSERT INTO observations (facet_id, source_type, source_ref, content, extracted_signal, signal_strength, signal_position, context, context_metadata, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "migration.risk_sensitivity",
                "session_behavioral",
                "session:session-001:2",
                "Keep OpenClaw active.",
                signal,
                0.78,
                0.91,
                "migration safety constraints",
                json.dumps({"tone": "serious"}),
                "2026-04-19T09:00:00+00:00",
            ),
        )
        conn.execute(
            "INSERT INTO traits (facet_id, value_position, confidence, observation_count, last_observation_at, last_synthesis_at, notes, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "migration.risk_sensitivity",
                trait_score,
                0.78,
                1,
                "2026-04-19T09:00:00+00:00",
                "2026-04-19T09:10:00+00:00",
                "Stable under migration stress.",
                "ok",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    (base_dir / "PORTRAIT.md").write_text(portrait, encoding="utf-8")


def test_shadow_run_script_exports_both_sides_and_generates_report(tmp_path: Path) -> None:
    openclaw_data = tmp_path / "openclaw_data"
    hermes_data = tmp_path / "hermes_data"
    out_dir = tmp_path / "shadow_out"
    portrait = (GOLDEN / "PORTRAIT.expected.md").read_text(encoding="utf-8")

    _seed_data_dir(
        openclaw_data,
        signal="The subject explicitly prioritizes zero-loss, reversible migration steps.",
        trait_score=0.91,
        portrait=portrait,
    )
    _seed_data_dir(
        hermes_data,
        signal="The subject explicitly prioritizes zero-loss, reversible migration steps.",
        trait_score=0.91,
        portrait=portrait,
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--openclaw-data-dir",
            str(openclaw_data),
            "--hermes-data-dir",
            str(hermes_data),
            "--out-dir",
            str(out_dir),
            "--golden-dir",
            str(GOLDEN),
            "--run-id",
            "shadow-run-ok",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (out_dir / "openclaw" / "observations.jsonl").is_file()
    assert (out_dir / "hermes" / "observations.jsonl").is_file()
    report = json.loads((out_dir / "shadow_report.json").read_text(encoding="utf-8"))
    assert report["run_id"] == "shadow-run-ok"
    assert report["rollback_required"] is False
