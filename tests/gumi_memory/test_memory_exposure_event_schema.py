"""PR19B — exposure event schema presence."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_schema_file_exists() -> None:
    p = ROOT / "schemas" / "memory_exposure_event.schema.json"
    assert p.exists()
    json.loads(p.read_text())
