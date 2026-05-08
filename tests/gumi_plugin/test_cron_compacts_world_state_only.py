"""PR22H — compactor must not invent autonomous events."""
from __future__ import annotations

from relic.gumi_plugin import ContinuityCompactor


def test_compact_diary_drops_deleted_entries() -> None:
    c = ContinuityCompactor()
    entries = [
        {"id": "1", "text": "ok"},
        {"id": "2", "text": "removed", "deleted": True},
    ]
    out = c.compact_diary(entries)
    assert all(not e.get("deleted") for e in out)
    assert {e["id"] for e in out} == {"1"}


def test_compact_world_state_truncates_large_strings() -> None:
    c = ContinuityCompactor(max_world_state_bytes=64)
    big = "x" * 1024
    out = c.compact_world_state({"a": big, "b": "small"})
    assert out["b"] == "small"
    assert out["a"].endswith("[truncated]")
