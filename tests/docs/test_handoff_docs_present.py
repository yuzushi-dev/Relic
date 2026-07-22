"""Root markdown contract for publishable OSS repo."""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

ROOT_MARKDOWN_ALLOWED = {
    "README.md",
    "SECURITY.md",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
    "CHANGELOG.md",
    "DESIGN.md",
}

INTERNAL_DOC_PREFIXES = [
    "NORMATIVE_INDEX",
    "ORCHESTRATOR_",
    "SUBAGENT_",
    "HANDOFF_",
    "ZERO_KNOWLEDGE_",
    "CODEX_",
    "AGENTS.",
    "TASKS.",
    "TEST_MATRIX",
]


def _published_root_markdown() -> set[str]:
    """Root markdown the repo actually ships.

    The contract is about what a reader of the public repo sees, so it has to
    look at tracked files rather than the working tree: gitignored local notes
    (CLAUDE.md and friends) never reach a clone and must not fail the check.
    """
    try:
        listing = subprocess.run(
            ["git", "-C", str(ROOT), "ls-files", "--", "*.md"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return {p.name for p in ROOT.glob("*.md")}
    return {name for name in listing.split() if "/" not in name}


def test_required_root_markdown_present() -> None:
    for name in ("README.md", "SECURITY.md"):
        p = ROOT / name
        assert p.exists(), f"missing required root markdown: {name}"
        assert p.stat().st_size > 0, f"empty: {name}"


def test_no_agentic_scaffolding_at_root() -> None:
    for name in _published_root_markdown():
        for prefix in INTERNAL_DOC_PREFIXES:
            assert not name.startswith(prefix), (
                f"agentic scaffolding doc found at root: {name}"
            )


def test_no_unexpected_markdown_at_root() -> None:
    unexpected = _published_root_markdown() - ROOT_MARKDOWN_ALLOWED
    assert not unexpected, f"unexpected markdown at root: {unexpected}"
