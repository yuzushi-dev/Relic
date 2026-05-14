"""Root markdown contract for publishable OSS repo."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

ROOT_MARKDOWN_ALLOWED = {
    "README.md",
    "SECURITY.md",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
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


def test_required_root_markdown_present() -> None:
    for name in ("README.md", "SECURITY.md"):
        p = ROOT / name
        assert p.exists(), f"missing required root markdown: {name}"
        assert p.stat().st_size > 0, f"empty: {name}"


def test_no_agentic_scaffolding_at_root() -> None:
    for md in ROOT.glob("*.md"):
        for prefix in INTERNAL_DOC_PREFIXES:
            assert not md.name.startswith(prefix), (
                f"agentic scaffolding doc found at root: {md.name}"
            )


def test_no_unexpected_markdown_at_root() -> None:
    actual = {p.name for p in ROOT.glob("*.md")}
    unexpected = actual - ROOT_MARKDOWN_ALLOWED
    assert not unexpected, f"unexpected markdown at root: {unexpected}"
