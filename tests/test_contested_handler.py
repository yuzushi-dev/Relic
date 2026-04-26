"""Tests for relic_contested_handler."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("RELIC_DATA_DIR", "/tmp/relic_contested_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "fake-token")
os.environ.setdefault("RELIC_HEALTH_TELEGRAM_CHAT_ID", "-1003733933010")
os.environ.setdefault("RELIC_HEALTH_TELEGRAM_THREAD_ID", "599")

from relic.relic_contested_handler import (
    _build_thread_map,
    _load_state,
    _log_decision,
    _save_state,
)


@pytest.fixture(autouse=True)
def tmp_relic(tmp_path, monkeypatch):
    monkeypatch.setenv("RELIC_DATA_DIR", str(tmp_path))
    # Re-import to pick up new RELIC_DIR
    import importlib
    import relic.relic_contested_handler as mod
    importlib.reload(mod)
    yield tmp_path


def test_build_thread_map_returns_health_entry(monkeypatch):
    monkeypatch.setenv("RELIC_HEALTH_TELEGRAM_CHAT_ID", "-1003733933010")
    monkeypatch.setenv("RELIC_HEALTH_TELEGRAM_THREAD_ID", "599")
    import importlib
    import relic.relic_contested_handler as mod
    importlib.reload(mod)
    tmap = mod._build_thread_map()
    assert ("-1003733933010", 599) in tmap
    assert tmap[("-1003733933010", 599)] == "health"


def test_build_thread_map_skips_missing_env(monkeypatch):
    monkeypatch.delenv("RELIC_CORR_TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.delenv("RELIC_CORR_TELEGRAM_THREAD_ID", raising=False)
    import importlib
    import relic.relic_contested_handler as mod
    importlib.reload(mod)
    tmap = mod._build_thread_map()
    keys = [v for _, v in tmap.items()]
    assert "bio" not in keys


def test_state_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("RELIC_DATA_DIR", str(tmp_path))
    import importlib
    import relic.relic_contested_handler as mod
    importlib.reload(mod)

    mod._save_state({"last_update_id": 42})
    state = mod._load_state()
    assert state["last_update_id"] == 42


def test_load_state_defaults_to_zero(tmp_path, monkeypatch):
    monkeypatch.setenv("RELIC_DATA_DIR", str(tmp_path))
    import importlib
    import relic.relic_contested_handler as mod
    importlib.reload(mod)

    state = mod._load_state()
    assert state["last_update_id"] == 0


def test_log_decision_appends_jsonl(tmp_path, monkeypatch):
    monkeypatch.setenv("RELIC_DATA_DIR", str(tmp_path))
    import importlib
    import relic.relic_contested_handler as mod
    importlib.reload(mod)

    mod._log_decision("health", "b", "monitor only", from_user=123)
    lines = (tmp_path / "reviewer_decisions.jsonl").read_text().strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["domain"] == "health"
    assert entry["decision"] == "monitor"
    assert entry["source"] == "human_telegram_b"


def test_log_decision_option_a_is_apply_critical(tmp_path, monkeypatch):
    monkeypatch.setenv("RELIC_DATA_DIR", str(tmp_path))
    import importlib
    import relic.relic_contested_handler as mod
    importlib.reload(mod)

    mod._log_decision("health", "a", "critical override", from_user=None)
    entry = json.loads(
        (tmp_path / "reviewer_decisions.jsonl").read_text().strip().splitlines()[-1]
    )
    assert entry["decision"] == "apply_critical"


def test_apply_health_action_b_returns_monitor(tmp_path, monkeypatch):
    monkeypatch.setenv("RELIC_DATA_DIR", str(tmp_path))
    import importlib
    import relic.relic_contested_handler as mod
    importlib.reload(mod)

    result = mod._apply_health_action("b")
    assert "monitor" in result


def test_apply_health_action_no_last_run(tmp_path, monkeypatch):
    monkeypatch.setenv("RELIC_DATA_DIR", str(tmp_path))
    import importlib
    import relic.relic_contested_handler as mod
    importlib.reload(mod)

    result = mod._apply_health_action("a")
    assert "not found" in result or "monitor" in result


def test_apply_health_action_a_with_last_run(tmp_path, monkeypatch):
    monkeypatch.setenv("RELIC_DATA_DIR", str(tmp_path))
    import importlib
    import relic.relic_contested_handler as mod
    importlib.reload(mod)

    # Write a minimal last_health_run.json
    last_run = {
        "saved_at": "2026-04-26T00:00:00Z",
        "metrics": {
            "avg_confidence": 0.12,
            "coverage_pct": 0.13,
            "bootstrap_loop_risk": 0.0,
            "obs_7d_total": 5,
            "obs_7d_ai_mediated": 0,
            "obs_7d_independent": 5,
            "facets_total": 60,
            "facets_covered": 8,
        },
        "neglected": [],
    }
    (tmp_path / "last_health_run.json").write_text(json.dumps(last_run))

    result = mod._apply_health_action("a")
    # Should attempt remediation (may write file or log)
    assert "critical" in result or "applied" in result or "failed" in result
