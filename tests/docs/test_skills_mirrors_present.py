"""PR22G — Gumi skills must be mirrored in skills/, .claude/skills/, .agents/skills/."""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ["gumi-roleplay-frame", "gumi-continuity-maintenance", "gumi-memory-evaluation"]


@pytest.mark.parametrize("skill", SKILLS)
@pytest.mark.parametrize("base", ["skills", ".claude/skills", ".agents/skills"])
def test_skill_mirror_exists(base: str, skill: str) -> None:
    base_path = ROOT / base
    if not base_path.exists():
        pytest.skip(f"{base} is local orchestration state and absent in publishable clones")
    p = ROOT / base / skill / "SKILL.md"
    assert p.exists(), f"missing {base}/{skill}/SKILL.md"
