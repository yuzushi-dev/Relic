"""On-disk storage for Gumi continuity artifacts (PR22D/PR22E).

Storage is local-only by design; every entry includes provenance.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class GumiStorage:
    root: Path

    def __post_init__(self) -> None:
        self.root = Path(self.root)
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "diary").mkdir(exist_ok=True)
        (self.root / "world_state").mkdir(exist_ok=True)

    def write_diary_entry(self, entry: dict[str, Any]) -> Path:
        eid = entry.get("entry_id") or entry.get("id") or "entry"
        path = self.root / "diary" / f"{eid}.json"
        path.write_text(json.dumps(entry, indent=2, ensure_ascii=False))
        return path

    def write_world_state(self, snapshot: dict[str, Any], name: str = "current") -> Path:
        path = self.root / "world_state" / f"{name}.json"
        path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False))
        return path

    def list_diary(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for p in sorted((self.root / "diary").glob("*.json")):
            try:
                out.append(json.loads(p.read_text()))
            except Exception:
                continue
        return out
