import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "hooks"

BASELINE_MARKERS = [
    "@gmail.com",
    "@hotmail.com",
    "@yahoo.com",
]

FORBIDDEN_MARKERS = BASELINE_MARKERS + [
    marker
    for marker in os.environ.get("RELIC_PRIVATE_MARKERS", "").splitlines()
    if marker.strip()
]


def iter_hook_sources() -> list[Path]:
    return sorted(ROOT.rglob("*.ts"))


def test_hook_sources_do_not_contain_local_paths_or_real_ids():
    offenders: list[str] = []
    for path in iter_hook_sources():
        text = path.read_text(encoding="utf-8")
        for marker in FORBIDDEN_MARKERS:
            if marker in text:
                offenders.append(f"{path.relative_to(ROOT.parent)} -> {marker}")

    assert offenders == []
