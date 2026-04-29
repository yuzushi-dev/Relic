from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "migration" / "live_owner_switch.py"


def _write_openclaw_jobs(path: Path) -> None:
    payload = {
        "version": 1,
        "jobs": [
            {
                "id": "openclaw-job",
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
    openclaw_jobs = tmp_path / "openclaw-jobs.json"
    hermes_jobs = tmp_path / "hermes-jobs.json"
    _write_openclaw_jobs(openclaw_jobs)
    _write_hermes_jobs(hermes_jobs)

    promote = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "promote",
            "--openclaw-jobs",
            str(openclaw_jobs),
            "--hermes-jobs",
            str(hermes_jobs),
            "--openclaw-job-id",
            "openclaw-job",
            "--hermes-job-id",
            "hermes-job",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert promote.returncode == 0, promote.stderr
    promoted_openclaw = json.loads(openclaw_jobs.read_text(encoding="utf-8"))
    promoted_hermes = json.loads(hermes_jobs.read_text(encoding="utf-8"))
    assert promoted_openclaw["jobs"][0]["enabled"] is False
    assert promoted_hermes["jobs"][0]["enabled"] is True
    assert promoted_hermes["jobs"][0]["state"] == "scheduled"
    summary = json.loads(promote.stdout)
    assert summary["mode"] == "promote"
    assert summary["dry_run"] is False
    assert summary["openclaw_after"]["enabled"] is False
    assert summary["hermes_after"]["enabled"] is True

    rollback = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "rollback",
            "--openclaw-jobs",
            str(openclaw_jobs),
            "--hermes-jobs",
            str(hermes_jobs),
            "--openclaw-job-id",
            "openclaw-job",
            "--hermes-job-id",
            "hermes-job",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert rollback.returncode == 0, rollback.stderr
    rolled_openclaw = json.loads(openclaw_jobs.read_text(encoding="utf-8"))
    rolled_hermes = json.loads(hermes_jobs.read_text(encoding="utf-8"))
    assert rolled_openclaw["jobs"][0]["enabled"] is True
    assert rolled_hermes["jobs"][0]["enabled"] is False
    assert rolled_hermes["jobs"][0]["state"] == "paused"
    summary = json.loads(rollback.stdout)
    assert summary["mode"] == "rollback"
    assert summary["openclaw_after"]["enabled"] is True
    assert summary["hermes_after"]["enabled"] is False


def test_live_owner_switch_dry_run_does_not_modify_files(tmp_path: Path) -> None:
    openclaw_jobs = tmp_path / "openclaw-jobs.json"
    hermes_jobs = tmp_path / "hermes-jobs.json"
    _write_openclaw_jobs(openclaw_jobs)
    _write_hermes_jobs(hermes_jobs)
    before_openclaw = openclaw_jobs.read_text(encoding="utf-8")
    before_hermes = hermes_jobs.read_text(encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "promote",
            "--dry-run",
            "--openclaw-jobs",
            str(openclaw_jobs),
            "--hermes-jobs",
            str(hermes_jobs),
            "--openclaw-job-id",
            "openclaw-job",
            "--hermes-job-id",
            "hermes-job",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert openclaw_jobs.read_text(encoding="utf-8") == before_openclaw
    assert hermes_jobs.read_text(encoding="utf-8") == before_hermes
    summary = json.loads(result.stdout)
    assert summary["dry_run"] is True
    assert summary["openclaw_before"]["enabled"] is True
    assert summary["openclaw_after"]["enabled"] is False
    assert summary["hermes_before"]["enabled"] is False
    assert summary["hermes_after"]["enabled"] is True
