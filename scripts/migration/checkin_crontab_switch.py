#!/usr/bin/env python3
"""Promote or rollback the crontab-owned Relic checkin path.

Environment variables used when building the hermes line:
  RELIC_WORKTREE      - path to the relic-oss checkout (default: current dir)
  RELIC_VENV          - path to the venv activate script
  RELIC_ENV_FILE      - path to the .env file sourced before running
  RELIC_DATA_DIR      - passed to python -m mnemon.checkin
  RELIC_LOG_PATH      - cron log file path
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

_WORKTREE = os.environ.get("RELIC_WORKTREE", str(Path(__file__).resolve().parents[2]))
_VENV = os.environ.get("RELIC_VENV", str(Path(_WORKTREE) / ".venv" / "bin" / "activate"))
_ENV_FILE = os.environ.get("RELIC_ENV_FILE", str(Path(_WORKTREE) / ".env"))
_DATA_DIR = os.environ.get("RELIC_DATA_DIR", "")
_LOG_PATH = os.environ.get("RELIC_LOG_PATH", "/tmp/relic-checkin.log")

HERMES_LINE_FRAGMENT = "python3 -m mnemon.checkin "


def build_hermes_line() -> str:
    data_dir_env = f"RELIC_DATA_DIR={_DATA_DIR} " if _DATA_DIR else ""
    return (
        "*/30 9-22 * * * "
        f"cd {_WORKTREE} && "
        f"source {_VENV} && "
        f"set -a && source {_ENV_FILE} && set +a && "
        f"PYTHONPATH=src {data_dir_env}"
        f"timeout 180 python3 -m mnemon.checkin "
        f">> {_LOG_PATH} 2>&1"
    )


def load_crontab_lines(path: Path | None = None) -> list[str]:
    if path is not None:
        return path.read_text(encoding="utf-8").splitlines()
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True, check=True)
    return result.stdout.splitlines()


def find_checkin_line(lines: list[str]) -> str:
    matches = [line for line in lines if HERMES_LINE_FRAGMENT in line]
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
        raise RuntimeError("rollback not supported after migration is complete")
    else:
        raise ValueError(f"unsupported mode: {mode}")
    updated = [replacement if line == current else line for line in lines]
    return "\n".join(updated) + ("\n" if content.endswith("\n") else "")


def apply_crontab(content: str) -> None:
    subprocess.run(["crontab", "-"], input=content, text=True, check=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Promote or rollback the crontab-owned Relic checkin path")
    parser.add_argument("mode", choices=["status", "promote"])
    parser.add_argument("--crontab-file", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    lines = load_crontab_lines(args.crontab_file)
    current = find_checkin_line(lines)

    if args.mode == "status":
        if HERMES_LINE_FRAGMENT in current:
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
