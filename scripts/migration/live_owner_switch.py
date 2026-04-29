from __future__ import annotations

import argparse
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _save_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _find_job(jobs: list[dict[str, Any]], job_id: str) -> dict[str, Any]:
    for job in jobs:
        if job.get("id") == job_id:
            return job
    raise SystemExit(f"job not found: {job_id}")


def _snapshot_openclaw(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": job.get("id"),
        "name": job.get("name"),
        "enabled": job.get("enabled"),
        "last_status": (job.get("state") or {}).get("lastStatus"),
        "next_run_at_ms": (job.get("state") or {}).get("nextRunAtMs"),
    }


def _snapshot_hermes(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": job.get("id"),
        "name": job.get("name"),
        "enabled": job.get("enabled"),
        "state": job.get("state"),
        "last_status": job.get("last_status"),
        "next_run_at": job.get("next_run_at"),
    }


def _apply_promote(openclaw_job: dict[str, Any], hermes_job: dict[str, Any]) -> None:
    openclaw_job["enabled"] = False
    hermes_job["enabled"] = True
    hermes_job["state"] = "scheduled"
    hermes_job["paused_at"] = None
    hermes_job["paused_reason"] = None


def _apply_rollback(openclaw_job: dict[str, Any], hermes_job: dict[str, Any]) -> None:
    openclaw_job["enabled"] = True
    hermes_job["enabled"] = False
    hermes_job["state"] = "paused"
    hermes_job["paused_at"] = _now_iso()
    hermes_job["paused_reason"] = "owner rollback"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare or apply a reversible owner switch for one OpenClaw/Hermes Wave 1 job pair."
    )
    parser.add_argument("mode", choices=["status", "promote", "rollback"])
    parser.add_argument("--openclaw-jobs", type=Path, required=True)
    parser.add_argument("--hermes-jobs", type=Path, required=True)
    parser.add_argument("--openclaw-job-id", required=True)
    parser.add_argument("--hermes-job-id", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    openclaw_payload = _load_json(args.openclaw_jobs)
    hermes_payload = _load_json(args.hermes_jobs)

    openclaw_jobs = openclaw_payload.get("jobs")
    hermes_jobs = hermes_payload.get("jobs")
    if not isinstance(openclaw_jobs, list) or not isinstance(hermes_jobs, list):
        raise SystemExit("unsupported jobs file structure")

    openclaw_job = _find_job(openclaw_jobs, args.openclaw_job_id)
    hermes_job = _find_job(hermes_jobs, args.hermes_job_id)

    before_openclaw = _snapshot_openclaw(openclaw_job)
    before_hermes = _snapshot_hermes(hermes_job)

    planned_openclaw = deepcopy(openclaw_job)
    planned_hermes = deepcopy(hermes_job)

    if args.mode == "promote":
        _apply_promote(planned_openclaw, planned_hermes)
    elif args.mode == "rollback":
        _apply_rollback(planned_openclaw, planned_hermes)

    after_openclaw = _snapshot_openclaw(planned_openclaw)
    after_hermes = _snapshot_hermes(planned_hermes)

    if args.mode != "status" and not args.dry_run:
        openclaw_job.update(planned_openclaw)
        hermes_job.update(planned_hermes)
        hermes_payload["updated_at"] = _now_iso()
        _save_json(args.openclaw_jobs, openclaw_payload)
        _save_json(args.hermes_jobs, hermes_payload)

    summary = {
        "mode": args.mode,
        "dry_run": args.dry_run,
        "openclaw_before": before_openclaw,
        "openclaw_after": after_openclaw,
        "hermes_before": before_hermes,
        "hermes_after": after_hermes,
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
