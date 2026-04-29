"""Tests for relic_contested_handler (rollback command handler)."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "fake-token")
os.environ.setdefault("RELIC_HEALTH_TELEGRAM_CHAT_ID", "-1003733933010")
os.environ.setdefault("RELIC_HEALTH_TELEGRAM_THREAD_ID", "599")


@pytest.fixture(autouse=True)
def tmp_relic(tmp_path, monkeypatch):
    monkeypatch.setenv("RELIC_DATA_DIR", str(tmp_path))
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
    assert "bio" not in tmap.values()


def test_state_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("RELIC_DATA_DIR", str(tmp_path))
    import importlib
    import relic.relic_contested_handler as mod
    importlib.reload(mod)

    mod._save_state({"last_update_id": 99})
    assert mod._load_state()["last_update_id"] == 99


def test_load_state_defaults_to_zero(tmp_path, monkeypatch):
    monkeypatch.setenv("RELIC_DATA_DIR", str(tmp_path))
    import importlib
    import relic.relic_contested_handler as mod
    importlib.reload(mod)

    assert mod._load_state()["last_update_id"] == 0


def test_log_rollback_appends_jsonl(tmp_path, monkeypatch):
    monkeypatch.setenv("RELIC_DATA_DIR", str(tmp_path))
    import importlib
    import relic.relic_contested_handler as mod
    importlib.reload(mod)

    mod._log_rollback("health", "Rolled back to snapshot 20260426_063720", from_user=42)
    lines = (tmp_path / "reviewer_decisions.jsonl").read_text().strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["domain"] == "health"
    assert entry["decision"] == "rollback"
    assert entry["source"] == "human_telegram_rollback"
    assert entry["telegram_user_id"] == 42


def test_do_rollback_no_snapshots(tmp_path, monkeypatch):
    monkeypatch.setenv("RELIC_DATA_DIR", str(tmp_path))
    import importlib
    import relic.relic_contested_handler as mod
    importlib.reload(mod)

    result = mod._do_rollback("health")
    assert "No snapshots" in result or "nothing" in result.lower()


def test_do_rollback_with_snapshot(tmp_path, monkeypatch):
    monkeypatch.setenv("RELIC_DATA_DIR", str(tmp_path))
    import importlib
    import relic.relic_contested_handler as mod
    importlib.reload(mod)

    # Create a snapshot directory and file
    snap_dir = tmp_path / "override_snapshots" / "health"
    snap_dir.mkdir(parents=True)
    snap_file = snap_dir / "20260426_063720.json"
    snap_file.write_text('{"severity": "degraded"}')

    result = mod._do_rollback("health")
    assert "20260426_063720" in result or "Rolled back" in result
