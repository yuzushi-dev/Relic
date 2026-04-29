from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "migration" / "shadow_compare.py"
GOLDEN = ROOT / "datasets" / "regression" / "golden_v1"


def _write_artifact_set(base_dir: Path, *, observation_signal: str, trait_score: float, portrait: str) -> None:
    base_dir.mkdir(parents=True, exist_ok=True)
    (base_dir / "observations.jsonl").write_text(
        json.dumps(
            {
                "facet_id": "migration.risk_sensitivity",
                "source_ref": "session:session-001:2",
                "extracted_signal": observation_signal,
                "signal_strength": 0.78,
                "signal_position": 0.91,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (base_dir / "traits.json").write_text(
        json.dumps(
            {
                "migration.risk_sensitivity": {
                    "score": trait_score,
                    "confidence": 0.78,
                    "evidence_count": 1,
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (base_dir / "PORTRAIT.md").write_text(portrait, encoding="utf-8")


def test_shadow_compare_treats_provenance_enriched_backfill_as_equivalent(tmp_path: Path) -> None:
    openclaw_dir = tmp_path / "openclaw"
    hermes_dir = tmp_path / "hermes"
    out_dir = tmp_path / "out"
    portrait = (GOLDEN / "PORTRAIT.expected.md").read_text(encoding="utf-8")

    openclaw_dir.mkdir(parents=True, exist_ok=True)
    hermes_dir.mkdir(parents=True, exist_ok=True)
    canonical_observation = {
        "facet_id": "migration.risk_sensitivity",
        "source_ref": "session:session-001:2",
        "extracted_signal": "The subject explicitly prioritizes zero-loss, reversible migration steps.",
        "signal_strength": 0.78,
        "signal_position": 0.91,
        "source_type": "passive_chat",
        "context": "The subject rejects unsafe cutover paths.",
        "context_metadata": {"channel": "telegram"},
        "created_at": "2026-04-19T10:00:00+00:00",
    }
    backfill_observation = {
        **canonical_observation,
        "context_metadata": {
            "channel": "telegram",
            "provenance": {
                "source_runtime": "openclaw",
                "source_session_id": "session-001",
                "source_message_ref": "2",
                "source_timestamp": "2026-04-19T10:00:00+00:00",
                "ingestion_mode": "backfill",
                "extractor_name": "historical_backfill",
                "extractor_version": "v1",
                "import_batch_id": "batch-001",
            },
        },
        "created_at": "2026-04-19T12:00:00+00:00",
    }
    (openclaw_dir / "observations.jsonl").write_text(
        json.dumps(canonical_observation, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (hermes_dir / "observations.jsonl").write_text(
        json.dumps(backfill_observation, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    traits = {
        "migration.risk_sensitivity": {
            "score": 0.91,
            "confidence": 0.78,
            "evidence_count": 1,
        }
    }
    (openclaw_dir / "traits.json").write_text(json.dumps(traits) + "\n", encoding="utf-8")
    (hermes_dir / "traits.json").write_text(json.dumps(traits) + "\n", encoding="utf-8")
    (openclaw_dir / "PORTRAIT.md").write_text(portrait, encoding="utf-8")
    (hermes_dir / "PORTRAIT.md").write_text(portrait, encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--openclaw-dir",
            str(openclaw_dir),
            "--hermes-dir",
            str(hermes_dir),
            "--out-dir",
            str(out_dir),
            "--golden-dir",
            str(GOLDEN),
            "--run-id",
            "shadow-backfill-equivalent",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    report = json.loads((out_dir / "shadow_report.json").read_text(encoding="utf-8"))
    assert report["observation_counts"]["mismatch_count"] == 0
    assert report["observation_mismatches"] == []
    assert report["rollback_required"] is False


def test_shadow_compare_script_generates_zero_mismatch_report(tmp_path: Path) -> None:
    openclaw_dir = tmp_path / "openclaw"
    hermes_dir = tmp_path / "hermes"
    out_dir = tmp_path / "out"
    portrait = (GOLDEN / "PORTRAIT.expected.md").read_text(encoding="utf-8")

    _write_artifact_set(
        openclaw_dir,
        observation_signal="The subject explicitly prioritizes zero-loss, reversible migration steps.",
        trait_score=0.91,
        portrait=portrait,
    )
    _write_artifact_set(
        hermes_dir,
        observation_signal="The subject explicitly prioritizes zero-loss, reversible migration steps.",
        trait_score=0.91,
        portrait=portrait,
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--openclaw-dir",
            str(openclaw_dir),
            "--hermes-dir",
            str(hermes_dir),
            "--out-dir",
            str(out_dir),
            "--golden-dir",
            str(GOLDEN),
            "--run-id",
            "shadow-ok",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    report = json.loads((out_dir / "shadow_report.json").read_text(encoding="utf-8"))
    assert report["run_id"] == "shadow-ok"
    assert report["canonical_runtime"] == "openclaw"
    assert report["shadow_runtime"] == "hermes"
    assert report["session_source"] == "hermes"
    assert report["observation_counts"]["openclaw"] == 1
    assert report["observation_counts"]["hermes"] == 1
    assert report["observation_counts"]["mismatch_count"] == 0
    assert report["missing_from_shadow"] == []
    assert report["unexpected_in_shadow"] == []
    assert report["trait_differences"] == []
    assert report["portrait_status"]["status"] == "match"
    assert report["artifact_gate_status"]["status"] == "pass"
    assert report["rollback_required"] is False


def test_shadow_compare_script_reports_observation_and_trait_mismatches(tmp_path: Path) -> None:
    openclaw_dir = tmp_path / "openclaw"
    hermes_dir = tmp_path / "hermes"
    out_dir = tmp_path / "out"

    _write_artifact_set(
        openclaw_dir,
        observation_signal="The subject explicitly prioritizes zero-loss, reversible migration steps.",
        trait_score=0.91,
        portrait="# Portrait\n\nStable canonical portrait.\n",
    )
    _write_artifact_set(
        hermes_dir,
        observation_signal="The subject accepts risky migration shortcuts.",
        trait_score=0.25,
        portrait="# Portrait\n\nDivergent shadow portrait.\n",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--openclaw-dir",
            str(openclaw_dir),
            "--hermes-dir",
            str(hermes_dir),
            "--out-dir",
            str(out_dir),
            "--golden-dir",
            str(GOLDEN),
            "--run-id",
            "shadow-mismatch",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    report = json.loads((out_dir / "shadow_report.json").read_text(encoding="utf-8"))
    assert report["observation_counts"]["mismatch_count"] == 1
    assert len(report["trait_differences"]) == 1
    assert report["portrait_status"]["status"] == "mismatch"
    assert report["rollback_required"] is True
