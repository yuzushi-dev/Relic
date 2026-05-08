"""Tests for Makefile target registry."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# All targets from TASKS.yaml as documented in the task packet
REQUIRED_TARGETS = [
    "help",
    "setup",
    "lint",
    "test",
    "test-db",
    "test-cac",
    "test-privacy",
    "test-correction",
    "test-compiler",
    "test-vault",
    "test-hermes-plugin",
    "test-eval",
    "test-ui",
    "test-memory-dynamics",
    "fixture-basic",
    "fixture-corrections",
    "fixture-privacy",
    "fixture-no-injection",
    "fixture-ui-validation",
    "fixture-memory-dynamics",
    "eval-baselines",
    "replication-bundle",
    "demo-e2e",
    "validate-design",
    "memory-dynamics-report",
    "setup-dry-run",
]


@pytest.fixture
def makefile_content() -> str:
    """Read Makefile content."""
    makefile_path = Path(__file__).parent.parent / "Makefile"
    return makefile_path.read_text()


def test_makefile_exists():
    """Makefile exists in project root."""
    makefile_path = Path(__file__).parent.parent / "Makefile"
    assert makefile_path.exists(), "Makefile must exist in project root"


def test_makefile_has_phony_targets(makefile_content: str):
    """Makefile has .PHONY declaring all targets."""
    phony_match = re.search(r"\.PHONY:\s*(.+)", makefile_content)
    assert phony_match, "Makefile must have .PHONY declaration"
    phony_targets = phony_match.group(1).split()
    for target in REQUIRED_TARGETS:
        assert target in phony_targets, f"Target '{target}' must be in .PHONY"


def test_makefile_has_all_targets(makefile_content: str):
    """Makefile defines all required targets."""
    for target in REQUIRED_TARGETS:
        pattern = rf"^{re.escape(target)}:"
        assert re.search(pattern, makefile_content, re.MULTILINE), \
            f"Target '{target}' must be defined in Makefile"


def test_makefile_help_target(makefile_content: str):
    """Makefile has help target with descriptions."""
    help_match = re.search(r"^help:.*?(?=^\S|\Z)", makefile_content, re.MULTILINE | re.DOTALL)
    assert help_match, "Makefile must have help target"
    help_text = help_match.group(0)
    for target in REQUIRED_TARGETS:
        if target != "help":
            assert target in help_text, f"Target '{target}' should be documented in help"


def test_makefile_test_db_target(makefile_content: str):
    """Makefile has working test-db target."""
    assert re.search(r"^test-db:", makefile_content, re.MULTILINE)
    # test-db should run pytest for db tests
    assert "pytest" in makefile_content.lower() or "PYTEST" in makefile_content


def test_makefile_lint_target(makefile_content: str):
    """Makefile has working lint target."""
    assert re.search(r"^lint:", makefile_content, re.MULTILINE)
    assert "ruff" in makefile_content.lower() or "RUFF" in makefile_content
