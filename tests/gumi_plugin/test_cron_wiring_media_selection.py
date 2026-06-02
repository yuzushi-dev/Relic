"""Tests for _select_media_type, policy fallback + voice/audio key compat."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

import pytest

from relic.gumi_plugin import cron_wiring


@pytest.fixture
def now() -> datetime:
    return datetime(2026, 5, 19, 12, 0, 0)


def _roll(subject_id: str, now: datetime) -> int:
    seed = f"{subject_id}|media|{now.date()}"
    return int(hashlib.sha256(seed.encode()).hexdigest(), 16) % 100


def _find_subject_with_roll(now: datetime, lo: int, hi: int) -> str:
    for i in range(100000):
        sid = f"subj{i}"
        if lo <= _roll(sid, now) < hi:
            return sid
    raise RuntimeError("no subject id found in band")


def _write_workspace_policy(hermes_home: Path, data: dict) -> Path:
    d = hermes_home / "workspace" / "gumi"
    d.mkdir(parents=True, exist_ok=True)
    p = d / "media_policy.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def _write_subject_policy(home: Path, subject_id: str, data: dict) -> Path:
    d = home / ".relic" / "subjects" / subject_id
    d.mkdir(parents=True, exist_ok=True)
    p = d / "gumi_media_policy.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


@pytest.fixture
def patches(monkeypatch):
    monkeypatch.setattr(cron_wiring, "_pro_media_allowed", lambda s, m: True)
    monkeypatch.setattr(cron_wiring, "is_media_eligible", lambda *a, **k: True)
    monkeypatch.setattr(cron_wiring, "last_media_ts", lambda *a, **k: now_recent())


def now_recent():
    return datetime(2026, 5, 18, 12, 0, 0)


def test_workspace_missing_falls_back_to_subject_and_mirrors(tmp_path, now, patches, monkeypatch):
    hermes_home = tmp_path / "hermes"
    hermes_home.mkdir()
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))
    # Only image is enabled; image band is roll < 50.
    _write_subject_policy(fake_home, "subj", {
        "image_generation_enabled": True,
        "audio_generation_enabled": False,
        "music_generation_enabled": False,
    })
    result = cron_wiring._select_media_type("subj", hermes_home, now)
    expected = "image" if _roll("subj", now) < 50 else "text"
    assert result == expected
    # mirror created
    assert (hermes_home / "workspace" / "gumi" / "media_policy.json").exists()


def test_workspace_and_subject_missing_returns_text(tmp_path, now, monkeypatch):
    hermes_home = tmp_path / "hermes"
    hermes_home.mkdir()
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))
    assert cron_wiring._select_media_type("subj", hermes_home, now) == "text"


def test_voice_eligible_via_legacy_audio_key(tmp_path, now, patches):
    hermes_home = tmp_path / "hermes"
    hermes_home.mkdir()
    _write_workspace_policy(hermes_home, {
        "image_generation_enabled": False,
        "audio_generation_enabled": True,
        "music_generation_enabled": False,
    })
    sid = _find_subject_with_roll(now, 0, 30)
    assert cron_wiring._select_media_type(sid, hermes_home, now) == "voice"


def test_voice_eligible_via_new_voice_key(tmp_path, now, patches):
    hermes_home = tmp_path / "hermes"
    hermes_home.mkdir()
    _write_workspace_policy(hermes_home, {
        "image_generation_enabled": False,
        "voice_generation_enabled": True,
        "music_generation_enabled": False,
    })
    sid = _find_subject_with_roll(now, 0, 30)
    assert cron_wiring._select_media_type(sid, hermes_home, now) == "voice"


def test_all_disabled_returns_text(tmp_path, now, patches):
    hermes_home = tmp_path / "hermes"
    hermes_home.mkdir()
    _write_workspace_policy(hermes_home, {
        "image_generation_enabled": False,
        "audio_generation_enabled": False,
        "voice_generation_enabled": False,
        "music_generation_enabled": False,
    })
    assert cron_wiring._select_media_type("subj", hermes_home, now) == "text"


def test_workspace_policy_corrupt_returns_text(tmp_path, now, patches):
    hermes_home = tmp_path / "hermes"
    hermes_home.mkdir()
    d = hermes_home / "workspace" / "gumi"
    d.mkdir(parents=True, exist_ok=True)
    (d / "media_policy.json").write_text("{not valid json", encoding="utf-8")
    assert cron_wiring._select_media_type("subj", hermes_home, now) == "text"


def test_mirror_content_identical_after_fallback(tmp_path, now, patches, monkeypatch):
    hermes_home = tmp_path / "hermes"
    hermes_home.mkdir()
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))
    subj_path = _write_subject_policy(fake_home, "subj", {
        "image_generation_enabled": True,
        "audio_generation_enabled": False,
        "music_generation_enabled": False,
    })
    cron_wiring._select_media_type("subj", hermes_home, now)
    mirror_path = hermes_home / "workspace" / "gumi" / "media_policy.json"
    assert mirror_path.read_bytes() == subj_path.read_bytes()
