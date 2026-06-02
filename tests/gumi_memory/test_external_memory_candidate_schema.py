"""PR19B, schema presence and required fields."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_schema_file_exists() -> None:
    p = ROOT / "schemas" / "external_memory_candidate.schema.json"
    assert p.exists()
    schema = json.loads(p.read_text())
    assert "properties" in schema
