"""PR13 — .codex/agents/*.toml must mirror reviewer roles."""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
REQUIRED = [
    "architecture-reviewer",
    "docs-handoff-writer",
    "evaluation-reviewer",
    "hermes-integration-reviewer",
    "implementation-worker",
    "replication-reviewer",
    "researcher-ui-reviewer",
    "roleplay-continuity-reviewer",
    "security-privacy-reviewer",
    "test-planner",
]


@pytest.mark.parametrize("name", REQUIRED)
def test_codex_agent_present(name: str) -> None:
    agents_dir = ROOT / ".codex" / "agents"
    if not agents_dir.exists():
        pytest.skip(".codex/agents is local orchestration state and absent in publishable clones")
    p = ROOT / ".codex" / "agents" / f"{name}.toml"
    assert p.exists(), f"missing .codex/agents/{name}.toml"
    body = p.read_text()
    assert "name" in body and "description" in body
