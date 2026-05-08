"""PR16D — Next.js workbench skeleton must exist."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_ui_package_json() -> None:
    assert (ROOT / "ui" / "package.json").exists()


def test_ui_next_config() -> None:
    configs = [
        ROOT / "ui" / "next.config.ts",
        ROOT / "ui" / "next.config.mjs",
    ]
    assert any(p.exists() for p in configs), "missing Next config (.ts or .mjs)"


def test_ui_workbench_page() -> None:
    assert (ROOT / "ui" / "app" / "workbench" / "page.tsx").exists()


def test_ui_design_tokens() -> None:
    assert (ROOT / "ui" / "design_tokens" / "tokens.json").exists()


def test_ui_playwright_tests_present() -> None:
    tests = list((ROOT / "ui" / "tests").glob("*.spec.ts"))
    assert len(tests) >= 4
