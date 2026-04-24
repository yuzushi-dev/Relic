import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src" / "relic"

BASELINE_MARKERS = [
    "@gmail.com",
    "@hotmail.com",
    "@yahoo.com",
    "biofeedback_creds.json",
]

FORBIDDEN_MARKERS = BASELINE_MARKERS + [
    marker
    for marker in os.environ.get("RELIC_PRIVATE_MARKERS", "").splitlines()
    if marker.strip()
]


def iter_python_files() -> list[Path]:
    return sorted(ROOT.rglob("*.py"))


def test_python_sources_do_not_contain_configured_private_markers():
    offenders: list[str] = []
    for path in iter_python_files():
        text = path.read_text(encoding="utf-8")
        for marker in FORBIDDEN_MARKERS:
            if marker in text:
                offenders.append(f"{path.relative_to(ROOT.parent)} -> {marker}")

    assert offenders == []
