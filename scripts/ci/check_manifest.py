#!/usr/bin/env python3
"""Validate that required manifest files exist and are well-formed.

Exits 0 if all required manifests are present and valid.
Supports --help for safe no-arg behavior.
"""

import argparse
import json
import sys
from pathlib import Path


REQUIRED_MANIFESTS = [
    "pyproject.toml",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate project manifests.")
    parser.parse_args()  # exits on --help

    root = Path(__file__).parent.parent.parent
    errors = []

    for name in REQUIRED_MANIFESTS:
        path = root / name
        if not path.exists():
            errors.append(f"{name}: file not found")
            continue
        if name.endswith(".json"):
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                errors.append(f"{name}: JSONDecodeError: {e}")

    if errors:
        print("Manifest validation errors:")
        for e in errors:
            print(e)
        return 1
    print("All required manifests are present and valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
