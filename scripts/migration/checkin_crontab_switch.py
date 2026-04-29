#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

CHECKIN_LOG_PATH = "/home/cristina/.openclaw/cron/runs/relic-checkin.log"
OPENCLAW_LINE_FRAGMENT = "python3 scripts/gumi_personal_checkin.py"
HERMES_LINE_FRAGMENT = "python3 -m relic.checkin "
WORKTREE = "/home/cristina/worktrees/relic-hermes-execution"
ENV_FILE = "/home/cristina/.openclaw/openclaw-relic/.env"


def build_hermes_line() -> str:
    return (
        "*/30 9-22 * * * "
        f"cd {WORKTREE} && "
        "source /home/cristina/.venv/bin/activate && "
        f"set -a && source {ENV_FILE} && set +a && "
        "PYTHONPATH=src OPENCLAW_HOME=/home/cristina/.openclaw "
        "RELIC_DATA_DIR=/home/cristina/.relic/daniele "
        "timeout 180 python3 -m relic.checkin "
        f">> {CHECKIN_LOG_PATH} 2>&1"
    )


def load_crontab_lines(path: Path | None = None) -> list[str]:
    if path is not None:
        return path.read_text(encoding="utf-8").splitlines()
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True, check=True)
    return result.stdout.splitlines()


def find_checkin_line(lines: list[str]) -> str:
    matches = [
        line for line in lines
        if OPENCLAW_LINE_FRAGMENT in line or HERMES_LINE_FRAGMENT in line
    ]
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one live checkin line, found {len(matches)}")
    return matches[0]


def transform_crontab(content: str, mode: str) -> str:
    lines = content.splitlines()
    current = find_checkin_line(lines)
    if mode == "promote":
        replacement = build_hermes_line()
        if HERMES_LINE_FRAGMENT in current:
            return content
    elif mode == "rollback":
        replacement = (
            "*/30 9-22 * * * "
            "cd /home/cristina/.openclaw/workspace-gumi && "
            "source /home/cristina/.venv/bin/activate && "
            f"set -a && source {ENV_FILE} && set +a && "
            "PYTHONPATH=/home/cristina/.openclaw/workspace/scripts "
            "OPENCLAW_HOME=/home/cristina/.openclaw "
            "timeout 180 python3 scripts/gumi_personal_checkin.py "
            f">> {CHECKIN_LOG_PATH} 2>&1"
        )
        if OPENCLAW_LINE_FRAGMENT in current:
            return content
    else:
        raise ValueError(f"unsupported mode: {mode}")
    updated = [replacement if line == current else line for line in lines]
    return "\n".join(updated) + ("\n" if content.endswith("\n") else "")


def apply_crontab(content: str) -> None:
    subprocess.run(["crontab", "-"], input=content, text=True, check=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Promote or rollback the crontab-owned Relic checkin path")
    parser.add_argument("mode", choices=["status", "promote", "rollback"])
    parser.add_argument("--crontab-file", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    lines = load_crontab_lines(args.crontab_file)
    current = find_checkin_line(lines)

    if args.mode == "status":
        if OPENCLAW_LINE_FRAGMENT in current:
            print("openclaw")
        elif HERMES_LINE_FRAGMENT in current:
            print("hermes")
        else:
            raise RuntimeError("unknown checkin owner line")
        return 0

    original = "\n".join(lines) + ("\n" if lines else "")
    updated = transform_crontab(original, mode=args.mode)
    if args.dry_run:
        print(updated)
        return 0

    if args.crontab_file is not None:
        args.crontab_file.write_text(updated, encoding="utf-8")
    else:
        apply_crontab(updated)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
