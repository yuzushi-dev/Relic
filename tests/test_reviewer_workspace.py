"""Tests for src/lib/reviewer_workspace.py"""
from __future__ import annotations

import json
from pathlib import Path


def test_export_debate_writes_files(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPERCLIP_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("PAPERCLIP_TEST_REVIEWER_ID", "test-reviewer-001")

    ws = tmp_path / "test-reviewer-001"
    ws.mkdir()

    from lib.reviewer_workspace import export_debate

    debate = {
        "domain": "health",
        "pro": {"argument": "arg", "model": "m"},
        "contra": {"argument": "arg2", "model": "m"},
        "judge": {"verdict": "intervene_soft", "rationale": "r", "confidence": 0.7},
        "generated_at": "2026-01-01T00:00:00+00:00",
    }
    extra = {"health_metrics": {"coverage_pct": 0.3}, "neglected_facets": [{"facet_id": "x"}]}

    export_debate(reviewer_id="test-reviewer-001", debate=debate, extra_files=extra)

    debate_file = ws / "debate.json"
    assert debate_file.exists()
    written = json.loads(debate_file.read_text())
    assert written["domain"] == "health"
    assert written["judge"]["verdict"] == "intervene_soft"

    assert (ws / "health_metrics.json").exists()
    assert (ws / "neglected_facets.json").exists()
    metrics = json.loads((ws / "health_metrics.json").read_text())
    assert metrics["coverage_pct"] == 0.3


def test_export_debate_skips_missing_workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPERCLIP_WORKSPACE_ROOT", str(tmp_path))

    from lib.reviewer_workspace import export_debate

    # Workspace directory does not exist — should not raise
    export_debate(
        reviewer_id="nonexistent-id",
        debate={"domain": "health", "pro": {}, "contra": {}, "judge": {}, "generated_at": ""},
        extra_files={},
    )


def test_export_debate_skips_empty_reviewer_id(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPERCLIP_WORKSPACE_ROOT", str(tmp_path))

    from lib.reviewer_workspace import export_debate

    export_debate(reviewer_id="", debate={}, extra_files={})
    # No files created
    assert list(tmp_path.iterdir()) == []
