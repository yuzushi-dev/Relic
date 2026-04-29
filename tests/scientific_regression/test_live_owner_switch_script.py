from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "migration" / "live_owner_switch.py"


def _write_canonical_jobs(path: Path) -> None:
    payload = {
        "version": 1,
        "jobs": [
            {
                "id": "canonical-job",
                "name": "relic:artifact-gate-check",
                "enabled": True,
                "state": {"lastStatus": "ok"},
            }
        ],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_hermes_jobs(path: Path) -> None:
    payload = {
        "updated_at": "2026-04-19T15:00:00+02:00",
        "jobs": [
            {
                "id": "hermes-job",
                "name": "wave1:relic:artifact-gate-check",
                "enabled": False,
                "state": "paused",
                "paused_at": "2026-04-19T15:00:00+02:00",
                "paused_reason": None,
            }
        ],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_live_owner_switch_promote_then_rollback(tmp_path: Path) -> None:
    canonical_jobs = tmp_path / "canonical-jobs.json"
    hermes_jobs = tmp_path / "hermes-jobs.json"
    _write_canonical_jobs(canonical_jobs)
    _write_hermes_jobs(hermes_jobs)

    promote = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "promote",
            "--canonical-jobs",
            str(canonical_jobs),
            "--hermes-jobs",
            str(hermes_jobs),
            "--canonical-job-id",
            "canonical-job",
            "--hermes-job-id",
            "hermes-job",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert promote.returncode == 0, promote.stderr
    promoted_canonical = json.loads(canonical_jobs.read_text(encoding="utf-8"))
    promoted_hermes = json.loads(hermes_jobs.read_text(encoding="utf-8"))
    assert promoted_canonical["jobs"][0]["enabled"] is False
    assert promoted_hermes["jobs"][0]["enabled"] is True
    assert promoted_hermes["jobs"][0]["state"] == "scheduled"
    summary = json.loads(promote.stdout)
    assert summary["mode"] == "promote"
    assert summary["dry_run"] is False
    assert summary["canonical_after"]["enabled"] is False
    assert summary["hermes_after"]["enabled"] is True

    rollback = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "rollback",
            "--canonical-jobs",
            str(canonical_jobs),
            "--hermes-jobs",
            str(hermes_jobs),
            "--canonical-job-id",
            "canonical-job",
            "--hermes-job-id",
            "hermes-job",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert rollback.returncode == 0, rollback.stderr
    rolled_canonical = json.loads(canonical_jobs.read_text(encoding="utf-8"))
    rolled_hermes = json.loads(hermes_jobs.read_text(encoding="utf-8"))
    assert rolled_canonical["jobs"][0]["enabled"] is True
    assert rolled_hermes["jobs"][0]["enabled"] is False
    assert rolled_hermes["jobs"][0]["state"] == "paused"
    summary = json.loads(rollback.stdout)
    assert summary["mode"] == "rollback"
    assert summary["canonical_after"]["enabled"] is True
    assert summary["hermes_after"]["enabled"] is False


def test_live_owner_switch_dry_run_does_not_modify_files(tmp_path: Path) -> None:
    canonical_jobs = tmp_path / "canonical-jobs.json"
    hermes_jobs = tmp_path / "hermes-jobs.json"
    _write_canonical_jobs(canonical_jobs)
    _write_hermes_jobs(hermes_jobs)
    before_canonical = canonical_jobs.read_text(encoding="utf-8")
    before_hermes = hermes_jobs.read_text(encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "promote",
            "--dry-run",
            "--canonical-jobs",
            str(canonical_jobs),
            "--hermes-jobs",
            str(hermes_jobs),
            "--canonical-job-id",
            "canonical-job",
            "--hermes-job-id",
            "hermes-job",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert canonical_jobs.read_text(encoding="utf-8") == before_canonical
    assert hermes_jobs.read_text(encoding="utf-8") == before_hermes
    summary = json.loads(result.stdout)
    assert summary["dry_run"] is True
    assert summary["canonical_before"]["enabled"] is True
    assert summary["canonical_after"]["enabled"] is False
    assert summary["hermes_before"]["enabled"] is False
    assert summary["hermes_after"]["enabled"] is True
