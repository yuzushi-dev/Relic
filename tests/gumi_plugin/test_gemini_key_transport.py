"""The Gemini API key must travel in a header, never in the request URL.

A key in the query string ends up in access logs, proxies and exception text.
"""
from __future__ import annotations

import base64
from pathlib import Path
from unittest.mock import MagicMock, patch

from relic.gumi_plugin.image_gen import generate_image, generate_image_prompt_via_llm
from relic.gumi_plugin.lyria import LyriaGenerator, verify_lyria_models
from relic.gumi_plugin.tts import synthesize

KEY = "SECRET-TEST-KEY"
HEADER = "x-goog-api-key"


def _assert_header_only(mock_call) -> None:
    mock_call.assert_called_once()
    args, kwargs = mock_call.call_args
    url = args[0] if args else kwargs["url"]
    assert KEY not in url and "key=" not in url
    assert kwargs["headers"][HEADER] == KEY


def _ok(payload: dict) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = payload
    return resp


def test_verify_lyria_models_uses_header():
    with patch("requests.get", return_value=_ok({"models": []})) as get:
        verify_lyria_models(KEY)
    _assert_header_only(get)


def test_lyria_call_uses_header(tmp_path: Path):
    audio = base64.b64encode(b"MP3").decode()
    payload = {"candidates": [{"content": {"parts": [{"inlineData": {"data": audio}}]}}]}
    gen = LyriaGenerator(tmp_path / "hermes", tmp_path / "relic", KEY)
    with patch("requests.post", return_value=_ok(payload)) as post:
        gen._call_lyria("a prompt")
    _assert_header_only(post)


def test_lyria_lyric_prompt_uses_header(tmp_path: Path):
    payload = {"candidates": [{"content": {"parts": [{"text": "prompt"}]}}]}
    gen = LyriaGenerator(tmp_path / "hermes", tmp_path / "relic", KEY)
    with patch("requests.post", return_value=_ok(payload)) as post:
        gen._build_lyric_prompt()
    _assert_header_only(post)


def test_tts_uses_header(tmp_path: Path):
    pcm = base64.b64encode(b"\x00" * 64).decode()
    payload = {"candidates": [{"content": {"parts": [{"inlineData": {"data": pcm}}]}}]}
    with patch("requests.post", return_value=_ok(payload)) as post, patch(
        "subprocess.run", return_value=MagicMock(returncode=0)
    ):
        try:
            synthesize("ciao", "Kore", tmp_path / "a.ogg", KEY)
        except Exception:  # noqa: BLE001 - only the outgoing request matters here
            pass
    _assert_header_only(post)


def test_image_generation_uses_header(tmp_path: Path):
    img = base64.b64encode(b"JPEG").decode()
    payload = {"candidates": [{"content": {"parts": [{"inline_data": {"data": img}}]}}]}
    with patch("requests.post", return_value=_ok(payload)) as post:
        generate_image("p", [], tmp_path / "o.jpg", KEY)
    _assert_header_only(post)


def test_image_prompt_via_llm_uses_header():
    payload = {"candidates": [{"content": {"parts": [{"text": "a prompt"}]}}]}
    with patch("requests.post", return_value=_ok(payload)) as post:
        generate_image_prompt_via_llm("spec", {}, "mode", KEY)
    _assert_header_only(post)
