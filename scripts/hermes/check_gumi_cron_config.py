#!/usr/bin/env python3
"""PR22H, verify the Gumi cron config matches schedule contract."""
from __future__ import annotations

import sys
from pathlib import Path

from relic.gumi_plugin.cron_schedule import ScheduleConfig


def main(path: str) -> int:
    p = Path(path)
    if not p.exists():
        print(f"MISSING {path}", file=sys.stderr)
        return 1
    try:
        import yaml

        cfg = yaml.safe_load(p.read_text()) or {}
    except Exception as exc:
        print(f"PARSE_ERROR {exc}", file=sys.stderr)
        return 2
    sc = ScheduleConfig(
        job_name=str(cfg.get("job_name", "")),
        cron=str(cfg.get("schedule", "")),
        timezone=str(cfg.get("timezone", "UTC")),
    )
    if not sc.validate():
        print(f"INVALID_CRON {sc.cron}", file=sys.stderr)
        return 3
    if cfg.get("allow_side_effects", False):
        print("FORBIDDEN allow_side_effects=true", file=sys.stderr)
        return 4
    print("OK", sc)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else ""))
