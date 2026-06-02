"""PR16C, replay must not mutate runtime artifacts."""
from __future__ import annotations

from pathlib import Path

from relic.ui.replay import replay_trace


def test_missing_trace_returns_failure() -> None:
    r = replay_trace("/nonexistent/path.jsonl")
    assert r.failure_reason == "trace_not_found"
    assert r.artifacts_changed == 0


def test_existing_trace_no_mutation(tmp_path: Path) -> None:
    p = tmp_path / "trace.jsonl"
    p.write_text('{"event_id": "1", "decision": "ALLOW"}\n')
    r = replay_trace(p)
    assert r.items_replayed == 1
    assert r.artifacts_changed == 0
    assert r.diffs[0]["noop"] is True
