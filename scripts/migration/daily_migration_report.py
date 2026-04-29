#!/usr/bin/env python3
"""Build and optionally send a daily Relic migration report."""

from __future__ import annotations

import argparse
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_ARTIFACTS_ROOT = Path("/home/cristina/docs/plans/live-artifacts")
DEFAULT_TARGET = "telegram:-1003733933010:142"


def _latest_snapshot_dir(artifacts_root: Path) -> Path:
    candidates = sorted(
        [path for path in artifacts_root.iterdir() if path.is_dir()],
        key=lambda path: path.name,
    )
    if not candidates:
        raise FileNotFoundError(f"no snapshot directories found under {artifacts_root}")
    return candidates[-1]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _target_parts(target: str) -> tuple[str, str]:
    if not target.startswith("telegram:"):
        raise ValueError("target must use telegram:chat_id:thread_id format")
    _, rest = target.split(":", 1)
    chat_id, thread_id = rest.rsplit(":", 1)
    if not chat_id or not thread_id:
        raise ValueError("target must include both chat_id and thread_id")
    return chat_id, thread_id


def build_report_text(snapshot_dir: Path) -> str:
    shadow_report = _load_json(snapshot_dir / "shadow-baseline" / "shadow_report.json")
    baseline_manifest = _load_json(snapshot_dir / "baseline_manifest.json")
    canonical_sync = _load_json(snapshot_dir / "canonical_state_sync.report.json")

    obs = shadow_report["observation_counts"]
    trait_diff_count = len(shadow_report.get("trait_differences", []))
    portrait_status = shadow_report.get("portrait_status", {}).get("status", "unknown")
    artifact_gate = shadow_report.get("artifact_gate_status", {}).get("status", "unknown")
    rollback_required = shadow_report.get("rollback_required", True)

    wave_canonical = baseline_manifest["wave_1_3"]["canonical_enabled"]
    wave_hermes = baseline_manifest["wave_1_3"]["hermes_active"]
    canonical_disabled = sum(1 for values in wave_canonical.values() if values == [False])
    hermes_active = sum(1 for active in wave_hermes.values() if active)

    user_paths = baseline_manifest["user_facing_paths"]
    sync_tables = canonical_sync.get("copied_tables", {})

    snapshot_name = snapshot_dir.name
    sync_rows = ", ".join(
        f"{table}={meta['rows_copied']}"
        for table, meta in sync_tables.items()
        if isinstance(meta, dict) and "rows_copied" in meta
    )

    return "\n".join(
        [
            f"Daily migration report {snapshot_name}",
            f"- shadow rollback_required: {'yes' if rollback_required else 'no'}",
            f"- observations: canonical={obs['canonical']} hermes={obs['hermes']} mismatches={obs['mismatch_count']}",
            f"- trait_differences: {trait_diff_count}",
            f"- portrait_status: {portrait_status}",
            f"- artifact_gate: {artifact_gate}",
            f"- Wave1-3 ownership: canonical_disabled={canonical_disabled}/17 hermes_active={hermes_active}/17",
            f"- user-facing: checkin_crontab={user_paths['crontab_checkin_present']} followup_crontab={user_paths['crontab_checkin_followup_present']} proactive_crontab={user_paths['crontab_proactive_present']}",
            f"- canonical store: checkin={user_paths['canonical_jobs_json_checkin_enabled']} followup={user_paths['canonical_jobs_json_checkin_followup_enabled']} proactive_placeholder={user_paths['canonical_jobs_json_gumi_proactive_enabled']}",
            f"- canonical sync rows: {sync_rows}",
            f"- artifacts: {snapshot_dir}",
        ]
    )


def send_telegram(text: str, *, target: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")
    chat_id, thread_id = _target_parts(target)
    payload = urllib.parse.urlencode(
        {
            "chat_id": chat_id,
            "message_thread_id": thread_id,
            "text": text,
        }
    ).encode()
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        response.read()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build and optionally send the daily migration report")
    parser.add_argument("--artifacts-root", type=Path, default=DEFAULT_ARTIFACTS_ROOT)
    parser.add_argument("--snapshot-dir", type=Path)
    parser.add_argument("--target", default=DEFAULT_TARGET)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    snapshot_dir = args.snapshot_dir or _latest_snapshot_dir(args.artifacts_root)
    text = build_report_text(snapshot_dir)
    print(text)
    if not args.dry_run:
        send_telegram(text, target=args.target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
