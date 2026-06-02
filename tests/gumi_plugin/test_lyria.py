"""Tests for lyria.py, music generation."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from relic.gumi_plugin.lyria import LyriaGenerator, verify_lyria_models


@pytest.fixture()
def lyria(tmp_path: Path) -> LyriaGenerator:
    hermes_home = tmp_path / "hermes"
    relic_home = tmp_path / "relic"
    hermes_home.mkdir()
    relic_home.mkdir()
    return LyriaGenerator(hermes_home, relic_home, "fake-api-key")


def test_can_generate_fresh_state(lyria: LyriaGenerator) -> None:
    ok, reason = lyria.can_generate()
    assert ok is True


def test_can_generate_recent_blocks(lyria: LyriaGenerator) -> None:
    state = {"last_generation": (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()}
    lyria._save_state(state)
    lyria._state = None  # reset cache
    ok, reason = lyria.can_generate()
    assert ok is False
    assert "Cooldown" in reason


def test_can_generate_floor_overrides(lyria: LyriaGenerator) -> None:
    state = {"last_generation": (datetime.now(timezone.utc) - timedelta(days=15)).isoformat()}
    lyria._save_state(state)
    lyria._state = None
    ok, reason = lyria.can_generate()
    assert ok is True
    assert "Floor" in reason or "elapsed" in reason.lower()


def test_generate_and_deliver_dry_run(lyria: LyriaGenerator) -> None:
    result = lyria.generate_and_deliver(target="test_user", dry_run=True)
    assert isinstance(result, dict)
    assert result.get("dry_run") is True
    assert "success" in result


def test_verify_lyria_models_parses(tmp_path: Path) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "models": [
            {"name": "models/lyria-3-clip-preview"},
            {"name": "models/lyria-realtime-exp"},
        ]
    }
    with patch("requests.get", return_value=mock_response):
        result = verify_lyria_models("fake-key")
    assert isinstance(result, dict)
    assert "lyria-3-clip-preview" in result
    # lyria-realtime-exp removed; only primary model tracked
    assert result["lyria-3-clip-preview"] is True
