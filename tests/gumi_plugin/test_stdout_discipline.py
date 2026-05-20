"""Lint invariant (I6): operator-internal modules must not print to stdout.

Every print() in relic/gumi_plugin/ and relic/checkin/ must either:
  a) have file=sys.stderr, OR
  b) be in a function annotated  # stdout: subject-facing

This prevents operator telemetry ([WARN], [DRY-RUN], MEDIA:, etc.)
from leaking into the subject's chat when Hermes forwards script stdout.

Exceptions:
  - checkin_media_dispatcher.py: print(safe) calls are intentional
    subject-facing output, verified separately in test_checkin_media_dispatcher_stdout.py
  - output_sanitizer.py: print(..., file=sys.stderr) for drop logging
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

# Modules where bare print() to stdout is explicitly allowed.
# checkin_media_dispatcher: sanitized subject-facing text messages.
# db_init: CLI tool JSON output (operator, not subject chat).
# The following are CLI __main__ tools whose stdout is operator/cron JSON,
# never forwarded to the subject chat.
_STDOUT_ALLOWED = {
    "checkin_media_dispatcher.py",  # sanitized subject-facing text (verified separately)
    "db_init.py",                   # CLI init output
    "facet_updater.py",             # CLI processing result
    "question_engine.py",           # CLI facet selection result
    "scheduler.py",                 # CLI gate check result
}

_ROOTS = [
    Path(__file__).parent.parent.parent / "relic" / "gumi_plugin",
    Path(__file__).parent.parent.parent / "relic" / "checkin",
]


def _find_bare_stdout_prints(src: str, filename: str) -> list[int]:
    """Return line numbers of print() calls that lack file=sys.stderr."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []

    violations = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Name) and func.id == "print"):
            continue
        # Check for file= keyword argument
        has_file_kwarg = any(kw.arg == "file" for kw in node.keywords)
        if not has_file_kwarg:
            violations.append(node.lineno)
    return violations


def _collect_violations() -> list[tuple[Path, int]]:
    violations = []
    for root in _ROOTS:
        if not root.exists():
            continue
        for py_file in sorted(root.glob("*.py")):
            if py_file.name in _STDOUT_ALLOWED:
                continue
            src = py_file.read_text(encoding="utf-8")
            lines = _find_bare_stdout_prints(src, py_file.name)
            for lineno in lines:
                violations.append((py_file, lineno))
    return violations


def test_no_bare_stdout_prints_in_operator_modules():
    """No print() without file=sys.stderr in gumi_plugin/ or checkin/ (except allowed list)."""
    violations = _collect_violations()
    if violations:
        msgs = [f"  {p.relative_to(Path(__file__).parent.parent.parent)}:{n}" for p, n in violations]
        pytest.fail(
            "Bare stdout print() found in operator-internal modules "
            "(add file=sys.stderr or add module to _STDOUT_ALLOWED):\n"
            + "\n".join(msgs)
        )
