from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "export_shadow_artifacts.py"


def _seed_shadow_data_dir(base_dir: Path) -> None:
    base_dir.mkdir(parents=True, exist_ok=True)
    db_path = base_dir / "relic.db"
    conn = sqlite3.connect(db_path)
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
                "The subject explicitly prioritizes zero-loss, reversible migration steps.",
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
                0.91,
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

    (base_dir / "PORTRAIT.md").write_text(
        "# Portrait\n\nThe subject consistently requests additive, reversible steps.\n",
        encoding="utf-8",
    )


def test_export_shadow_artifacts_script_exports_db_and_portrait(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    out_dir = tmp_path / "out"
    _seed_shadow_data_dir(data_dir)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--data-dir",
            str(data_dir),
            "--out-dir",
            str(out_dir),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    observations = (out_dir / "observations.jsonl").read_text(encoding="utf-8").splitlines()
    traits = json.loads((out_dir / "traits.json").read_text(encoding="utf-8"))
    portrait = (out_dir / "PORTRAIT.md").read_text(encoding="utf-8")

    assert len(observations) == 1
    assert json.loads(observations[0])["facet_id"] == "migration.risk_sensitivity"
    assert traits["migration.risk_sensitivity"]["score"] == 0.91
    assert "additive, reversible steps" in portrait


def test_export_shadow_artifacts_script_requires_portrait_and_db(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    out_dir = tmp_path / "out"
    data_dir.mkdir()

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--data-dir",
            str(data_dir),
            "--out-dir",
            str(out_dir),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "missing required input" in result.stderr.lower()
