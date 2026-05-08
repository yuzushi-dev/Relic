#!/usr/bin/env python3
"""Validate JSON and JSONL fixture files.

Exits 0 if all valid, 1 if parse errors.
Supports --help for safe no-arg behavior.
"""

import argparse
import json
import sys
from pathlib import Path

SKIP_DIRS = {
    ".agents",
    ".claude",
    ".codex",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "artifacts",
    "dev_docs",
    "dist",
    "build",
    "node_modules",
}


def should_skip(path: Path) -> bool:
    """Return True for local-only, generated, or dependency paths."""
    return any(part in SKIP_DIRS for part in path.parts)


def validate_jsonl(path: Path) -> list[str]:
    """Return list of errors in JSONL file."""
    errors = []
    try:
        with open(path, encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    json.loads(line)
                except json.JSONDecodeError as e:
                    errors.append(f"{path}:{line_no}: JSONDecodeError: {e}")
    except Exception as e:
        errors.append(f"{path}: read error: {e}")
    return errors


def validate_json(path: Path) -> list[str]:
    """Return list of errors in JSON file."""
    errors = []
    try:
        with open(path, encoding="utf-8") as f:
            json.load(f)
    except json.JSONDecodeError as e:
        errors.append(f"{path}: JSONDecodeError: {e}")
    except Exception as e:
        errors.append(f"{path}: read error: {e}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate JSON and JSONL fixtures.")
    parser.parse_args()  # exits on --help

    root = Path(__file__).parent.parent.parent
    errors = []

    for path in root.glob("**/*.jsonl"):
        if should_skip(path):
            continue
        errors.extend(validate_jsonl(path))

    for path in root.glob("**/*.json"):
        if should_skip(path) or path.name == "package-lock.json":
            continue
        errors.extend(validate_json(path))

    if errors:
        print("JSON/JSONL validation errors:")
        for e in errors:
            print(e)
        return 1
    print("All JSON/JSONL files are valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
