"""Tests for tts.py, Gemini TTS synthesis."""
from __future__ import annotations

import base64
import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from relic.gumi_plugin.tts import select_voice_for_canon, synthesize


def test_select_voice_female_warm() -> None:
    profile = {
        "domains": {
            "embodiment": {"gender_expression": "feminine"},
            "relationship_stance": {"attachment_style": "secure attachment"},
        }
    }
    assert select_voice_for_canon(profile) == "Aoede"


def test_select_voice_male_calm() -> None:
    profile = {
        "domains": {
            "embodiment": {"gender_expression": "masculine"},
            "relationship_stance": {"attachment_style": "avoidant attachment"},
        }
    }
    assert select_voice_for_canon(profile) == "Fenrir"


def test_select_voice_default_on_unknown() -> None:
    result = select_voice_for_canon({"gender": "unknown", "tone": "???"})
    assert result == "Kore"


def test_select_voice_missing_fields() -> None:
    result = select_voice_for_canon({})
    assert result == "Kore"


def test_synthesize_writes_ogg(tmp_path: Path) -> None:
    fake_pcm = base64.b64encode(b"\x00" * 1024).decode()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candidates": [{"content": {"parts": [{"inlineData": {"data": fake_pcm}}]}}]
    }

    fake_ogg = tmp_path / "out.ogg"
    fake_ogg.write_bytes(b"OGG")

    output = tmp_path / "audio.ogg"
    with patch("requests.post", return_value=mock_response), \
         patch("subprocess.run") as mock_sub:
        mock_sub.return_value = MagicMock(returncode=0)
        # ffmpeg writes to output_path in the real implementation via tmp
        # We just verify it was called
        result = synthesize("Ciao!", "Kore", output, "fake-key")

    mock_sub.assert_called_once()
    call_args = mock_sub.call_args[0][0]
    assert "ffmpeg" in call_args


def test_synthesize_raises_on_api_error(tmp_path: Path) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"

    output = tmp_path / "audio.ogg"
    with patch("requests.post", return_value=mock_response):
        with pytest.raises(RuntimeError, match="TTS"):
            synthesize("Ciao!", "Kore", output, "bad-key")


def test_synthesize_raises_on_missing_ffmpeg(tmp_path: Path) -> None:
    fake_pcm = base64.b64encode(b"\x00" * 100).decode()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candidates": [{"content": {"parts": [{"inlineData": {"data": fake_pcm}}]}}]
    }

    output = tmp_path / "audio.ogg"
    with patch("requests.post", return_value=mock_response), \
         patch("subprocess.run", side_effect=FileNotFoundError("ffmpeg")):
        with pytest.raises((RuntimeError, FileNotFoundError)):
            synthesize("Ciao!", "Kore", output, "fake-key")
