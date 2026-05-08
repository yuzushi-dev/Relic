#!/usr/bin/env python3
"""Check that no raw private data markers appear in fixtures or source.

Exits 0 if clean, 1 if private markers found.
Supports --help for safe no-arg behavior.
"""

import argparse
import re
import sys
from pathlib import Path


PRIVATE_MARKERS = [
    r"\bAPI_KEY\s*=\s*['\"]sk-[a-zA-Z0-9]",
    r"\b(?:ANTHROPIC|OPENAI|GEMINI)_API_KEY\s*=\s*['\"](?!PLACEHOLDER|REDACTED|\.\.\.)",
    r"\bhoncho_api_key\s*[:=]\s*['\"](?!PLACEHOLDER|REDACTED|\.\.\.)",
    r"\bhindsight_token\s*[:=]\s*['\"](?!PLACEHOLDER|REDACTED|\.\.\.)",
    r"\bbyterover_token\s*[:=]\s*['\"](?!PLACEHOLDER|REDACTED|\.\.\.)",
]

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
SKIP_PATH_PREFIXES = ["scripts/ci/"]

PATTERNS = [re.compile(p, re.IGNORECASE) for p in PRIVATE_MARKERS]


def check_file(path: Path) -> list[str]:
    """Return list of violations found in file."""
    violations = []
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return violations
    for line_no, line in enumerate(content.splitlines(), 1):
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        for pattern in PATTERNS:
            if pattern.search(line):
                redacted = line[:80].replace(str(Path.home()), "$HOME")
                violations.append(f"{path}:{line_no}: {redacted}")
    return violations


def should_skip(root: Path, path: Path) -> bool:
    """Return True for local-only, generated, dependency, or CI helper paths."""
    if any(part in SKIP_DIRS for part in path.parts):
        return True
    path_str = str(path.relative_to(root))
    return any(path_str.startswith(skip) for skip in SKIP_PATH_PREFIXES)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check no raw private data markers.")
    parser.parse_args()  # exits on --help

    root = Path(__file__).parent.parent.parent
    violations = []
    for pattern_str in ["**/*.jsonl", "**/*.json", "**/*.py", "**/*.md"]:
        for path in root.glob(pattern_str):
            if should_skip(root, path):
                continue
            violations.extend(check_file(path))

    if violations:
        print("Private data markers found:")
        for v in violations:
            print(v)
        return 1
    print("No raw private data markers found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
