"""Tests for media_state.py, cooldown tracking."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from relic.gumi_plugin.media_state import (
    DEFAULT_COOLDOWN_DAYS,
    is_media_eligible,
    last_media_ts,
    load_media_state,
    record_media_delivery,
    save_media_state,
)


@pytest.fixture()
def hermes_home(tmp_path: Path) -> Path:
    return tmp_path / "hermes"


def test_fresh_state_all_eligible(hermes_home: Path) -> None:
    for mtype in ("image", "voice", "music"):
        assert is_media_eligible(hermes_home, mtype) is True


def test_record_makes_ineligible(hermes_home: Path) -> None:
    now = datetime.now(timezone.utc)
    record_media_delivery(hermes_home, "image")
    assert is_media_eligible(hermes_home, "image", now=now) is False
    assert is_media_eligible(hermes_home, "voice", now=now) is True


def test_cooldown_elapsed_eligible(hermes_home: Path) -> None:
    record_media_delivery(hermes_home, "image")
    future = datetime.now(timezone.utc) + timedelta(days=3)
    assert is_media_eligible(hermes_home, "image", now=future) is True


def test_voice_cooldown_shorter(hermes_home: Path) -> None:
    record_media_delivery(hermes_home, "voice")
    after_1day = datetime.now(timezone.utc) + timedelta(hours=25)
    assert is_media_eligible(hermes_home, "voice", now=after_1day) is True
    before_1day = datetime.now(timezone.utc) + timedelta(hours=10)
    assert is_media_eligible(hermes_home, "voice", now=before_1day) is False


def test_atomic_write_no_corruption(hermes_home: Path) -> None:
    state = {"last_image_ts": "2026-01-01T00:00:00+00:00"}
    save_media_state(hermes_home, state)
    loaded = load_media_state(hermes_home)
    assert loaded["last_image_ts"] == "2026-01-01T00:00:00+00:00"
    tmp = (hermes_home / "state" / "media_delivery_state.tmp")
    assert not tmp.exists()


def test_last_media_ts_returns_none_on_missing(hermes_home: Path) -> None:
    assert last_media_ts(hermes_home, "music") is None


def test_corrupt_state_returns_empty(hermes_home: Path) -> None:
    path = hermes_home / "state" / "media_delivery_state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("NOT JSON", encoding="utf-8")
    assert load_media_state(hermes_home) == {}
