"""Tests for recent-outbound continuity surfacing (BUGCHAT fix)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from relic.hermes_plugin.recent_outbound import (
    build_recent_outbound_context,
    is_maintenance_session,
    recent_delivered_messages,
)


def _write_session(sessions_dir, name, messages, mtime: datetime | None = None):
    path = sessions_dir / name
    path.write_text(json.dumps({"messages": messages}), encoding="utf-8")
    if mtime is not None:
        ts = mtime.timestamp()
        import os
        os.utime(path, (ts, ts))
    return path


def _delivery(text):
    return [
        {"role": "user", "content": "[IMPORTANT: cron job...]\n## Script Output\n..."},
        {"role": "assistant", "content": text},
    ]


def _maintenance():
    return [
        {"role": "user", "content": "[IMPORTANT: cron job...] Review the workspace"},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "1"}]},
        {"role": "tool", "name": "read_file", "content": "{...}"},
        {"role": "assistant", "content": "Workspace compaction review — 7 candidates"},
    ]


def test_is_maintenance_session_detects_tool_use():
    assert is_maintenance_session({"messages": _maintenance()}) is True
    assert is_maintenance_session({"messages": _delivery("ciao")}) is False


def test_recent_delivered_excludes_maintenance(tmp_path):
    sd = tmp_path / "sessions"
    sd.mkdir()
    now = datetime(2026, 5, 30, 20, 36, tzinfo=timezone.utc)
    _write_session(sd, "session_cron_aaa_1.json", _delivery("messaggio reale"),
                   mtime=now - timedelta(minutes=5))
    _write_session(sd, "session_cron_bbb_2.json", _maintenance(),
                   mtime=now - timedelta(minutes=2))

    msgs = recent_delivered_messages(tmp_path, within_hours=6, now=now)
    texts = [m["text"] for m in msgs]
    assert texts == ["messaggio reale"]
    assert all("compaction" not in t for t in texts)


def test_recent_delivered_respects_window_and_order(tmp_path):
    sd = tmp_path / "sessions"
    sd.mkdir()
    now = datetime(2026, 5, 30, 20, 36, tzinfo=timezone.utc)
    _write_session(sd, "session_cron_old_1.json", _delivery("vecchio"),
                   mtime=now - timedelta(hours=72))
    _write_session(sd, "session_cron_mid_2.json", _delivery("primo"),
                   mtime=now - timedelta(hours=5))
    _write_session(sd, "session_cron_new_3.json", _delivery("secondo"),
                   mtime=now - timedelta(hours=1))

    msgs = recent_delivered_messages(tmp_path, within_hours=48, now=now)
    texts = [m["text"] for m in msgs]
    # newest-first, out-of-window 'vecchio' excluded
    assert texts == ["secondo", "primo"]


def test_skip_silent_and_empty(tmp_path):
    sd = tmp_path / "sessions"
    sd.mkdir()
    now = datetime(2026, 5, 30, 20, 36, tzinfo=timezone.utc)
    _write_session(sd, "session_cron_s_1.json", _delivery("[SILENT]"),
                   mtime=now - timedelta(minutes=10))
    _write_session(sd, "session_cron_e_2.json", _delivery("   "),
                   mtime=now - timedelta(minutes=5))
    assert recent_delivered_messages(tmp_path, within_hours=6, now=now) == []


def test_clean_strips_composer_scaffold(tmp_path):
    sd = tmp_path / "sessions"
    sd.mkdir()
    now = datetime(2026, 5, 30, 20, 36, tzinfo=timezone.utc)
    content = "caption: guarda il tramonto\nimage_prompt: a long english prompt here\ntipo: image"
    _write_session(sd, "session_cron_m_1.json", _delivery(content),
                   mtime=now - timedelta(minutes=5))
    msgs = recent_delivered_messages(tmp_path, within_hours=6, now=now)
    assert msgs[0]["text"] == "guarda il tramonto"


def test_build_block_empty_when_nothing(tmp_path):
    sd = tmp_path / "sessions"
    sd.mkdir()
    assert build_recent_outbound_context(tmp_path) == ""


def test_build_block_contains_messages(tmp_path):
    sd = tmp_path / "sessions"
    sd.mkdir()
    now = datetime(2026, 5, 30, 20, 36, tzinfo=timezone.utc)
    _write_session(sd, "session_cron_x_1.json", _delivery("domanda sulla gerarchia"),
                   mtime=now - timedelta(minutes=5))
    block = build_recent_outbound_context(tmp_path, within_hours=6, now=now)
    assert "domanda sulla gerarchia" in block
    assert "inviato tu" in block


def test_missing_sessions_dir_is_safe(tmp_path):
    assert recent_delivered_messages(tmp_path) == []
    assert build_recent_outbound_context(tmp_path) == ""
