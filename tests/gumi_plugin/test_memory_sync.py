"""Tests for gumi_memory_sync (memory_sync.py)."""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from relic.gumi_plugin.memory_sync import (
    _BLOCK_BEGIN,
    _BLOCK_END,
    _MAX_ENTRIES,
    _read_watermark,
    _write_watermark,
    _delivery_enabled,
    _parse_session_filename,
    _extract_outbound_entries,
    _scan_sessions,
    _read_existing_entries,
    _build_block,
    _rewrite_memory_block,
    sync,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session(path: Path, messages: list[dict], job_id: str = "job_abc") -> Path:
    """Write a fake session_cron_<jobid>_<ts>.json with the given messages."""
    ts = int(time.time())
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"messages": messages}
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _assistant_msg(content: str, ts: float | None = None) -> dict:
    msg = {"role": "assistant", "content": content}
    if ts is not None:
        msg["ts"] = ts
    return msg


def _user_msg(content: str) -> dict:
    return {"role": "user", "content": content}


# ---------------------------------------------------------------------------
# _parse_session_filename
# ---------------------------------------------------------------------------

def test_parse_session_filename_valid() -> None:
    name = "session_cron_checkin_gate_1234567890.json"
    result = _parse_session_filename(name)
    assert result is not None
    assert result[1] == "checkin_gate"

    name2 = "session_cron_job_xyz_9876543210.json"
    result2 = _parse_session_filename(name2)
    assert result2 is not None
    assert result2[1] == "job_xyz"


def test_parse_session_filename_invalid() -> None:
    assert _parse_session_filename("session_chat_123.json") is None
    assert _parse_session_filename("session_cron_.json") is None
    assert _parse_session_filename("regular_file.json") is None


# ---------------------------------------------------------------------------
# _extract_outbound_entries
# ---------------------------------------------------------------------------

def test_extract_outbound_entries_skips_silent() -> None:
    path = Path("/tmp/fake_session.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"messages": [
        _assistant_msg("[SILENT]"),
        _assistant_msg("Hello world!"),
    ]}), encoding="utf-8")

    entries = _extract_outbound_entries(path, "sid", "jobid", 0)
    assert len(entries) == 1
    assert entries[0]["text"] == "Hello world!"


def test_extract_outbound_entries_skips_error_delivery_status() -> None:
    path = Path("/tmp/fake_session2.json")
    path.write_text(json.dumps({"messages": [
        _assistant_msg("Hello", ts=1000.0),
    ]}), encoding="utf-8")

    # Manually corrupt the stored msg with error status
    data = json.loads(path.read_text())
    data["messages"][0]["result"] = {"delivery_status": "error"}
    path.write_text(json.dumps(data), encoding="utf-8")

    entries = _extract_outbound_entries(path, "sid", "jobid", 0)
    # Error delivery status should be skipped
    assert len(entries) == 0


def test_extract_outbound_entries_skips_empty_role() -> None:
    path = Path("/tmp/fake_session3.json")
    path.write_text(json.dumps({"messages": [
        _user_msg("hello"),
        _assistant_msg("Ciao!"),
    ]}), encoding="utf-8")

    entries = _extract_outbound_entries(path, "sid", "jobid", 0)
    assert len(entries) == 1
    assert entries[0]["text"] == "Ciao!"


def test_extract_outbound_entries_starts_from_index() -> None:
    path = Path("/tmp/fake_session4.json")
    path.write_text(json.dumps({"messages": [
        _assistant_msg("First"),
        _assistant_msg("Second"),
        _assistant_msg("Third"),
    ]}), encoding="utf-8")

    entries = _extract_outbound_entries(path, "sid", "jobid", start_idx=1)
    assert len(entries) == 2
    assert entries[0]["text"] == "Second"
    assert entries[1]["text"] == "Third"


def test_extract_outbound_entries_corrupted_json() -> None:
    path = Path("/tmp/fake_broken.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{ not json", encoding="utf-8")

    entries = _extract_outbound_entries(path, "sid", "jobid", 0)
    assert entries == []


# ---------------------------------------------------------------------------
# _delivery_enabled
# ---------------------------------------------------------------------------

def test_delivery_enabled_true_by_default(tmp_path: Path) -> None:
    hermes = tmp_path
    # No relationship_policy.md → default True
    assert _delivery_enabled(hermes) is True


def test_delivery_enabled_true_when_not_disabled(tmp_path: Path) -> None:
    hermes = tmp_path
    policy = hermes / "workspace" / "gumi"
    policy.mkdir(parents=True)
    (policy / "relationship_policy.md").write_text(
        "Some policy content\nwithout the flag\n", encoding="utf-8"
    )
    assert _delivery_enabled(hermes) is True


def test_delivery_enabled_false_when_flagged(tmp_path: Path) -> None:
    hermes = tmp_path
    policy = hermes / "workspace" / "gumi"
    policy.mkdir(parents=True)
    (policy / "relationship_policy.md").write_text(
        "delivery_enabled: false\n", encoding="utf-8"
    )
    assert _delivery_enabled(hermes) is False


# ---------------------------------------------------------------------------
# Watermark round-trip
# ---------------------------------------------------------------------------

def test_watermark_default(tmp_path: Path) -> None:
    wm = _read_watermark(tmp_path)
    assert wm["last_session_mtime_ns"] == 0
    assert wm["last_message_idx_per_session"] == {}

    _write_watermark(tmp_path, wm)
    assert (tmp_path / "memory_sync_watermark.json").exists()


def test_watermark_persists_last_idx(tmp_path: Path) -> None:
    wm = {"last_session_mtime_ns": 123, "last_message_idx_per_session": {"s1": 5, "s2": 2}}
    _write_watermark(tmp_path, wm)
    loaded = _read_watermark(tmp_path)
    assert loaded["last_message_idx_per_session"] == {"s1": 5, "s2": 2}


# ---------------------------------------------------------------------------
# sync(), integration-level
# ---------------------------------------------------------------------------

def test_sync_missing_memory_returns_no_memory(tmp_path: Path) -> None:
    hermes = tmp_path / "hermes_home"
    hermes.mkdir()
    (hermes / "sessions").mkdir()
    result = sync(hermes)
    assert result["skipped"] == "no_memory"
    assert result["done"] is False


def test_sync_missing_hermes_home_returns_no_hermes_home(tmp_path: Path) -> None:
    result = sync(tmp_path / "does_not_exist")
    assert result["skipped"] == "no_hermes_home"
    assert result["done"] is False


def test_sync_no_sessions_is_noop(tmp_path: Path) -> None:
    hermes = tmp_path / "hermes"
    hermes.mkdir()
    (hermes / "MEMORY.md").write_text("# MEMORY\n\nSome existing content.\n", encoding="utf-8")
    (hermes / "sessions").mkdir()
    (hermes / "state").mkdir()

    result = sync(hermes)
    assert result["scanned"] == 0
    assert result["appended"] == 0
    assert result["done"] is True
    # MEMORY.md unchanged
    assert "gumi:memory_sync" not in (hermes / "MEMORY.md").read_text(encoding="utf-8")


def test_sync_first_run_appends_block(tmp_path: Path) -> None:
    hermes = tmp_path / "hermes"
    hermes.mkdir()
    (hermes / "MEMORY.md").write_text("# MEMORY\n\nPre-existing line.\n", encoding="utf-8")
    sessions_dir = hermes / "sessions"
    sessions_dir.mkdir()

    now = time.time()
    _make_session(sessions_dir / "session_cron_checkin_msg_1234567890.json", [
        _user_msg("Ciao"),
        _assistant_msg("Ciao Daniele! Come stai oggi?"),
    ], job_id="checkin_msg")

    result = sync(hermes)
    assert result["scanned"] == 1
    assert result["appended"] == 1
    assert result["done"] is True

    memory = (hermes / "MEMORY.md").read_text(encoding="utf-8")
    assert _BLOCK_BEGIN in memory
    assert _BLOCK_END in memory
    assert "Ciao Daniele! Come stai oggi?" in memory
    assert "Pre-existing line" in memory  # pre-existing content preserved


def test_sync_idempotent_second_run_noops(tmp_path: Path) -> None:
    hermes = tmp_path / "hermes"
    hermes.mkdir()
    (hermes / "MEMORY.md").write_text("# MEMORY\n\nPre-existing line.\n", encoding="utf-8")
    sessions_dir = hermes / "sessions"
    sessions_dir.mkdir()
    state_dir = hermes / "state"
    state_dir.mkdir()

    session_path = sessions_dir / "session_cron_checkin_msg_1234567890.json"
    _make_session(session_path, [
        _user_msg("Ciao"),
        _assistant_msg("Ciao Daniele!"),
    ], job_id="checkin_msg")

    # First sync
    result1 = sync(hermes)
    assert result1["appended"] == 1

    # Second sync: no new sessions → nothing to append
    result2 = sync(hermes)
    assert result2["scanned"] == 0
    assert result2["appended"] == 0


def test_sync_new_message_delta_appended(tmp_path: Path) -> None:
    hermes = tmp_path / "hermes"
    hermes.mkdir()
    (hermes / "MEMORY.md").write_text("# MEMORY\n\nPre-existing line.\n", encoding="utf-8")
    sessions_dir = hermes / "sessions"
    sessions_dir.mkdir()

    session_path = sessions_dir / "session_cron_checkin_msg_1234567890.json"
    _make_session(session_path, [
        _user_msg("Ciao"),
        _assistant_msg("First message"),
    ], job_id="checkin_msg")
    sync(hermes)

    # Add a new session (or extend the same one with more messages)
    time.sleep(0.01)
    session2_path = sessions_dir / "session_cron_checkin_msg_9999999999.json"
    _make_session(session2_path, [
        _user_msg("ciao"),
        _assistant_msg("Second message"),
    ], job_id="checkin_msg")

    result = sync(hermes)
    assert result["appended"] == 1  # only the new one

    memory = (hermes / "MEMORY.md").read_text(encoding="utf-8")
    assert "First message" in memory
    assert "Second message" in memory


def test_sync_cap_at_20_entries(tmp_path: Path) -> None:
    import os
    hermes = tmp_path / "hermes"
    hermes.mkdir()
    (hermes / "MEMORY.md").write_text("# MEMORY\n\n", encoding="utf-8")
    sessions_dir = hermes / "sessions"
    sessions_dir.mkdir()

    ts_base = 1700000000
    # Create 25 sessions with strictly ascending mtimes
    for i in range(25):
        p = sessions_dir / f"session_cron_job_{i:03d}_1234567890.json"
        _make_session(p, [_assistant_msg(f"Message {i}")], job_id=f"job_{i}")
        mtime_ns = int((ts_base + i) * 1e9)
        os.utime(p, ns=(mtime_ns, mtime_ns))

    result = sync(hermes)
    assert result["scanned"] == 25
    assert result["appended"] == 25  # all 25 new entries appended (block is capped on rewrite)

    memory = hermes / "MEMORY.md"
    memory_text = memory.read_text(encoding="utf-8")
    # Newest 20 entries (indices 5-24) should be present
    assert "Message 24" in memory_text
    assert "Message 5" in memory_text
    assert "Message 4" not in memory_text
    assert "Message 0" not in memory_text
def test_sync_manual_seed_block_preserved(tmp_path: Path) -> None:
    hermes = tmp_path / "hermes"
    hermes.mkdir()
    # Pre-seed a block manually
    (hermes / "MEMORY.md").write_text(
        f"# MEMORY\n\n{_BLOCK_BEGIN}\n### 2025-01-01 12:00 (job=manual)\n> Manual entry.\n{_BLOCK_END}\n\nRest of memory.\n",
        encoding="utf-8",
    )
    sessions_dir = hermes / "sessions"
    sessions_dir.mkdir()

    session_path = sessions_dir / "session_cron_job_auto_1234567890.json"
    _make_session(session_path, [
        _user_msg("ciao"),
        _assistant_msg("Auto entry"),
    ], job_id="job_auto")

    result = sync(hermes)
    assert result["appended"] == 1

    memory = (hermes / "MEMORY.md").read_text(encoding="utf-8")
    assert "Manual entry" in memory
    assert "Auto entry" in memory
    assert "Rest of memory" in memory

    # The block should be replaced (not duplicated)
    assert memory.count(_BLOCK_BEGIN) == 1
    assert memory.count(_BLOCK_END) == 1


def test_sync_delivery_disabled_skips(tmp_path: Path) -> None:
    hermes = tmp_path / "hermes"
    hermes.mkdir()
    (hermes / "MEMORY.md").write_text("# MEMORY\n\n", encoding="utf-8")
    (hermes / "sessions").mkdir()
    (hermes / "workspace" / "gumi").mkdir(parents=True)
    (hermes / "workspace" / "gumi" / "relationship_policy.md").write_text(
        "delivery_enabled: false\n", encoding="utf-8"
    )

    result = sync(hermes)
    assert result["skipped"] == "delivery_disabled"
    assert result["done"] is False


def test_sync_corrupted_session_skipped(tmp_path: Path) -> None:
    hermes = tmp_path / "hermes"
    hermes.mkdir()
    (hermes / "MEMORY.md").write_text("# MEMORY\n\n", encoding="utf-8")
    sessions_dir = hermes / "sessions"
    sessions_dir.mkdir()

    # Valid session
    session_ok = sessions_dir / "session_cron_job_ok_1111111111.json"
    _make_session(session_ok, [_assistant_msg("OK message")], job_id="job_ok")

    # Corrupted session
    session_bad = sessions_dir / "session_cron_job_bad_2222222222.json"
    session_bad.parent.mkdir(parents=True, exist_ok=True)
    session_bad.write_text("{ not json", encoding="utf-8")

    result = sync(hermes)
    assert result["scanned"] == 1  # only the valid one
    assert result["appended"] == 1  # corrupted session produces no entries (not counted as error)
