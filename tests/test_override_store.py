"""Unit tests for relic_override_store."""
import json
import time
from pathlib import Path

import pytest
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from relic.relic_override_store import (
    MAX_SNAPSHOTS,
    snapshot_before_write,
    list_snapshots,
    restore_snapshot,
    clear_override,
    get_active_overrides,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _write_override(path: Path, severity: str = "degraded", **extra) -> None:
    from datetime import datetime, timezone, timedelta
    data = {
        "severity": severity,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=25)).isoformat(),
        **extra,
    }
    path.write_text(json.dumps(data))


# ── snapshot_before_write ─────────────────────────────────────────────────────

def test_snapshot_returns_none_if_file_absent(tmp_path):
    f = tmp_path / "overrides.json"
    result = snapshot_before_write(f, "health", tmp_path)
    assert result is None


def test_snapshot_saves_copy_when_file_exists(tmp_path):
    f = tmp_path / "overrides.json"
    _write_override(f)
    snap = snapshot_before_write(f, "health", tmp_path)
    assert snap is not None
    assert snap.exists()
    data = json.loads(snap.read_text())
    assert data["severity"] == "degraded"


def test_snapshot_saved_in_correct_directory(tmp_path):
    f = tmp_path / "overrides.json"
    _write_override(f)
    snap = snapshot_before_write(f, "humanness", tmp_path)
    assert "override_snapshots" in str(snap)
    assert "humanness" in str(snap)


def test_snapshot_does_not_delete_original(tmp_path):
    f = tmp_path / "overrides.json"
    _write_override(f)
    snapshot_before_write(f, "health", tmp_path)
    assert f.exists()


def test_snapshot_prunes_beyond_max(tmp_path):
    f = tmp_path / "overrides.json"
    snap_dir = tmp_path / "override_snapshots" / "health"
    snap_dir.mkdir(parents=True)
    # Crea MAX_SNAPSHOTS + 5 file fittizi
    for i in range(MAX_SNAPSHOTS + 5):
        (snap_dir / f"2026010{i:02d}_000000.json").write_text("{}")
    _write_override(f)
    snapshot_before_write(f, "health", tmp_path)
    remaining = list(snap_dir.glob("*.json"))
    assert len(remaining) <= MAX_SNAPSHOTS


# ── list_snapshots ────────────────────────────────────────────────────────────

def test_list_snapshots_empty_when_no_dir(tmp_path):
    assert list_snapshots(tmp_path, "health") == []


def test_list_snapshots_returns_most_recent_first(tmp_path):
    f = tmp_path / "overrides.json"
    # Crea due snapshot con write separate
    _write_override(f, severity="degraded")
    snapshot_before_write(f, "health", tmp_path)
    time.sleep(0.01)
    _write_override(f, severity="critical")
    snapshot_before_write(f, "health", tmp_path)

    snaps = list_snapshots(tmp_path, "health")
    assert len(snaps) == 2
    # più recente prima
    assert snaps[0]["timestamp"] >= snaps[1]["timestamp"]


def test_list_snapshots_contains_expected_fields(tmp_path):
    f = tmp_path / "overrides.json"
    _write_override(f, no_bullet_points=True)
    snapshot_before_write(f, "humanness", tmp_path)
    snaps = list_snapshots(tmp_path, "humanness")
    assert len(snaps) == 1
    s = snaps[0]
    assert "timestamp" in s
    assert "severity" in s
    assert "constraints" in s
    assert "path" in s


# ── get_active_overrides ──────────────────────────────────────────────────────

def test_get_active_overrides_returns_none_when_absent(tmp_path):
    assert get_active_overrides(tmp_path / "missing.json") is None


def test_get_active_overrides_returns_data_when_valid(tmp_path):
    f = tmp_path / "overrides.json"
    _write_override(f, severity="critical")
    data = get_active_overrides(f)
    assert data is not None
    assert data["severity"] == "critical"


def test_get_active_overrides_returns_none_when_expired(tmp_path):
    from datetime import datetime, timezone, timedelta
    f = tmp_path / "overrides.json"
    data = {
        "severity": "degraded",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
    }
    f.write_text(json.dumps(data))
    assert get_active_overrides(f) is None


# ── restore_snapshot ──────────────────────────────────────────────────────────

def test_restore_snapshot_error_when_no_snapshots(tmp_path):
    f = tmp_path / "overrides.json"
    result = restore_snapshot(tmp_path, "health", f)
    assert "error" in result


def test_restore_snapshot_restores_latest(tmp_path):
    f = tmp_path / "overrides.json"
    _write_override(f, severity="degraded")
    snapshot_before_write(f, "health", tmp_path)

    # Sovrascrivi con stato diverso
    _write_override(f, severity="critical")

    result = restore_snapshot(tmp_path, "health", f)
    assert "error" not in result
    assert result["severity"] == "degraded"
    data = json.loads(f.read_text())
    assert data["severity"] == "degraded"


def test_restore_snapshot_by_timestamp(tmp_path):
    f = tmp_path / "overrides.json"
    _write_override(f, severity="degraded")
    snap = snapshot_before_write(f, "health", tmp_path)
    ts = snap.stem

    _write_override(f, severity="critical")
    result = restore_snapshot(tmp_path, "health", f, timestamp=ts)
    assert result["restored"] == ts
    assert json.loads(f.read_text())["severity"] == "degraded"


def test_restore_snapshot_invalid_timestamp_returns_error(tmp_path):
    f = tmp_path / "overrides.json"
    _write_override(f)
    snapshot_before_write(f, "health", tmp_path)
    result = restore_snapshot(tmp_path, "health", f, timestamp="99991231_999999")
    assert "error" in result


def test_restore_snapshot_saves_current_before_restoring(tmp_path):
    f = tmp_path / "overrides.json"
    _write_override(f, severity="degraded")
    snapshot_before_write(f, "health", tmp_path)
    _write_override(f, severity="critical")

    restore_snapshot(tmp_path, "health", f)

    snaps = list_snapshots(tmp_path, "health")
    severities = {s["severity"] for s in snaps}
    assert "critical" in severities


# ── clear_override ────────────────────────────────────────────────────────────

def test_clear_override_removes_file(tmp_path):
    f = tmp_path / "overrides.json"
    _write_override(f)
    result = clear_override(tmp_path, "health", f)
    assert result["status"] == "cleared"
    assert not f.exists()


def test_clear_override_saves_snapshot_before_removal(tmp_path):
    f = tmp_path / "overrides.json"
    _write_override(f, severity="critical")
    clear_override(tmp_path, "health", f)
    snaps = list_snapshots(tmp_path, "health")
    assert len(snaps) == 1
    assert snaps[0]["severity"] == "critical"


def test_clear_override_already_clear(tmp_path):
    f = tmp_path / "overrides.json"
    result = clear_override(tmp_path, "health", f)
    assert result["status"] == "already_clear"
