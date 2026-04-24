"""Layer 4 artifact-gate regression tests.

Whitepaper §5.3 and §10 ('Sixth' design implication): only artifacts on
an explicit whitelist may be injected into agent bootstrap. This keeps
higher-order analysis outputs (schemas, defenses, CAPS, etc.) from
reaching downstream agents by accident.

The gate lives in ``hooks/shared/artifact-gate.ts`` and is consumed by
``hooks/relic-bootstrap/handler.ts``. The tests here are
source-level (no TS runtime required): they assert the gate is defined,
the bootstrap handler imports it, and the whitelist is conservative.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GATE_PATH = ROOT / "hooks" / "shared" / "artifact-gate.ts"
BOOTSTRAP_PATH = ROOT / "hooks" / "relic-bootstrap" / "handler.ts"


def test_artifact_gate_module_exists() -> None:
    assert GATE_PATH.is_file(), (
        f"Expected artifact-gate module at {GATE_PATH.relative_to(ROOT)}"
    )


def test_artifact_gate_exports_whitelist_and_predicate() -> None:
    src = GATE_PATH.read_text(encoding="utf-8")
    assert "INJECTABLE_ARTIFACTS" in src, "whitelist constant must be exported"
    assert "isInjectableArtifact" in src, "predicate function must be exported"


def test_whitelist_contains_portrait_only() -> None:
    """Bootstrap whitelist must be minimal: PORTRAIT.md is the only artifact
    the whitepaper §5.3 designates for agent-session injection."""
    src = GATE_PATH.read_text(encoding="utf-8")
    match = re.search(
        r"INJECTABLE_ARTIFACTS\s*(?::[^=]+)?=\s*\[([^\]]+)\]", src
    )
    assert match, "Could not locate INJECTABLE_ARTIFACTS array literal"
    items = re.findall(r"[\"']([^\"']+)[\"']", match.group(1))
    assert items == ["PORTRAIT.md"], (
        f"Whitelist must contain exactly ['PORTRAIT.md']; got {items!r}. "
        "Adding entries here is a governance decision - keep the list "
        "short and justified."
    )


def test_bootstrap_handler_imports_gate() -> None:
    src = BOOTSTRAP_PATH.read_text(encoding="utf-8")
    assert "artifact-gate" in src, (
        "bootstrap handler must import from shared/artifact-gate"
    )
    assert "isInjectableArtifact" in src, (
        "bootstrap handler must call isInjectableArtifact before reading"
    )


def test_bootstrap_uses_gate_before_reading_portrait() -> None:
    """The gate check must happen before the file read. This is a
    source-order check, not a runtime check, but it catches the most
    common refactor mistake."""
    src = BOOTSTRAP_PATH.read_text(encoding="utf-8")
    gate_idx = src.find("isInjectableArtifact")
    read_idx = src.find("readFile")
    assert gate_idx != -1 and read_idx != -1
    assert gate_idx < read_idx, (
        "isInjectableArtifact must be invoked before readFile(profilePath)"
    )


@pytest.mark.parametrize(
    "forbidden",
    [
        "PROFILE.md",
        "schemas.json",
        "defenses.json",
        "caps.json",
        "appraisal.json",
        "attachment.json",
    ],
)
def test_whitelist_excludes_layer3_and_profile(forbidden: str) -> None:
    """Higher-order specialist outputs (Layer 3) and the inspection-only
    PROFILE.md must not be bootstrap-injectable without an explicit
    design decision."""
    src = GATE_PATH.read_text(encoding="utf-8")
    match = re.search(
        r"INJECTABLE_ARTIFACTS\s*(?::[^=]+)?=\s*\[([^\]]+)\]", src
    )
    assert match
    items = re.findall(r"[\"']([^\"']+)[\"']", match.group(1))
    assert forbidden not in items, (
        f"{forbidden} must not be in the bootstrap whitelist"
    )
