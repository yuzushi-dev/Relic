"""Tests for checkin_media_dispatcher.py."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from relic.gumi_plugin.checkin_media_dispatcher import (
    clean_image_caption,
    dispatch,
    ensure_checkin_question_mark,
    parse_gate_output,
)


def test_parse_gate_output_voice() -> None:
    raw = "DELIVER\ntipo: voice\nora: 09:15 CEST\nCiao come stai?"
    result = parse_gate_output(raw)
    assert result["tipo"] == "voice"
    assert result["testo"] == "DELIVER\nCiao come stai?"


def test_ensure_checkin_question_mark_inserts_before_trailing_emoji() -> None:
    text = "Quando scopri qualcosa di nuovo, vai più di pancia o ti fai prima un'idea chiara 🎵"

    result = ensure_checkin_question_mark(text)

    assert result == "Quando scopri qualcosa di nuovo, vai più di pancia o ti fai prima un'idea chiara? 🎵"


def test_dispatch_checkin_music_does_not_force_question_mark(
    tmp_path: Path,
    capsys: pytest.CaptureFixture,
) -> None:
    hermes_home = tmp_path / "hermes"
    relic_home = tmp_path / "relic"
    hermes_home.mkdir()
    relic_home.mkdir()

    llm_output = "DELIVER\ntipo: music\nora: 09:00 CEST\nwarm ambient prompt"

    mock_generator = MagicMock()
    mock_generator.generate_and_deliver.return_value = {
        "success": True,
        "caption": "Warm track",
        "audio_path": str(tmp_path / "track.mp3"),
    }

    with patch("relic.gumi_plugin.checkin_media_dispatcher._get_api_key", return_value="fake-key"), \
         patch("relic.gumi_plugin.checkin_media_dispatcher.LyriaGenerator", return_value=mock_generator), \
         patch("relic.gumi_plugin.checkin_media_dispatcher.record_media_delivery"), \
         patch("relic.gumi_plugin.checkin_media_dispatcher._send_telegram_media", return_value=False):
        result = dispatch(
            llm_output,
            hermes_home,
            relic_home,
            "test_subject",
            decision_type="checkin",
        )

    capsys.readouterr()
    assert result["tipo"] == "music"
    assert result["success"] is True
    assert mock_generator.generate_and_deliver.call_args.kwargs["lyria_prompt"] == "DELIVER\nwarm ambient prompt"


def test_clean_image_caption_removes_only_trailing_periods() -> None:
    assert clean_image_caption("Sto cucinando.") == "Sto cucinando"
    assert clean_image_caption("Ti va di raccontarmelo?") == "Ti va di raccontarmelo?"
    assert clean_image_caption("guardo fuori,") == "guardo fuori,"


def test_parse_gate_output_image() -> None:
    raw = "DELIVER\ntipo: image\nora: 10:00 CEST\nStamattina ho sistemato la scrivania"
    result = parse_gate_output(raw)
    assert result["tipo"] == "image"
    assert "scrivania" in result["testo"]


def test_parse_gate_output_text_default() -> None:
    raw = "DELIVER\nora: 20:00 CEST\nBuonasera!"
    result = parse_gate_output(raw)
    assert result["tipo"] == "text"
    assert "Buonasera" in result["testo"]


def test_parse_gate_output_music() -> None:
    raw = "DELIVER\ntipo: music\nora: 21:00 CEST"
    result = parse_gate_output(raw)
    assert result["tipo"] == "music"


def test_dispatch_text_prints_to_stdout(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    hermes_home = tmp_path / "hermes"
    relic_home = tmp_path / "relic"
    hermes_home.mkdir()
    relic_home.mkdir()

    llm_output = "DELIVER\ntipo: text\nora: 10:00 CEST\nBuongiorno!"
    result = dispatch(llm_output, hermes_home, relic_home, "test_subject")
    captured = capsys.readouterr()
    assert "Buongiorno" in captured.out
    assert result["tipo"] == "text"
    assert result["success"] is True


def test_dispatch_voice_with_mock(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    hermes_home = tmp_path / "hermes"
    relic_home = tmp_path / "relic"
    hermes_home.mkdir()
    relic_home.mkdir()

    fake_audio = tmp_path / "audio.ogg"
    fake_audio.write_bytes(b"OGG")

    llm_output = "DELIVER\ntipo: voice\nora: 09:00 CEST\nCome stai oggi?"

    with patch("relic.gumi_plugin.checkin_media_dispatcher._get_api_key", return_value="fake-key"), \
         patch("relic.gumi_plugin.checkin_media_dispatcher.synthesize_checkin_audio", return_value=fake_audio), \
         patch("relic.gumi_plugin.checkin_media_dispatcher.record_media_delivery"):
        result = dispatch(llm_output, hermes_home, relic_home, "test_subject")

    captured = capsys.readouterr()
    # Voice delivered via Telegram Bot API — stdout must be empty (immersion contract)
    assert captured.out == ""
    assert f"MEDIA:{fake_audio}" in captured.err
    assert result["tipo"] == "voice"


def test_dispatch_image_with_mock(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    hermes_home = tmp_path / "hermes"
    relic_home = tmp_path / "relic"
    hermes_home.mkdir()
    relic_home.mkdir()

    fake_image = tmp_path / "image.jpg"
    fake_image.write_bytes(b"JPEG")

    llm_output = "DELIVER\ntipo: image\nora: 10:00 CEST\nOggi ho sistemato la scrivania"

    with patch("relic.gumi_plugin.checkin_media_dispatcher._get_api_key", return_value="fake-key"), \
         patch("relic.gumi_plugin.checkin_media_dispatcher.generate_checkin_image", return_value=fake_image), \
         patch("relic.gumi_plugin.checkin_media_dispatcher.record_media_delivery"):
        result = dispatch(llm_output, hermes_home, relic_home, "test_subject")

    captured = capsys.readouterr()
    # Image + caption delivered directly via Telegram Bot API — stdout must be empty
    assert captured.out == ""
    assert f"MEDIA:{fake_image}" in captured.err
    assert result["tipo"] == "image"


def test_dispatch_music_with_mock(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    hermes_home = tmp_path / "hermes"
    relic_home = tmp_path / "relic"
    hermes_home.mkdir()
    relic_home.mkdir()

    fake_audio = tmp_path / "music.ogg"
    fake_audio.write_bytes(b"OGG")

    llm_output = "DELIVER\ntipo: music\nora: 21:00 CEST"

    mock_lyria = MagicMock()
    mock_lyria.generate_and_deliver.return_value = {
        "success": True,
        "audio_path": str(fake_audio),
        "caption": "Una melodia per questa sera",
    }

    with patch("relic.gumi_plugin.checkin_media_dispatcher._get_api_key", return_value="fake-key"), \
         patch("relic.gumi_plugin.checkin_media_dispatcher.LyriaGenerator", return_value=mock_lyria), \
         patch("relic.gumi_plugin.checkin_media_dispatcher.record_media_delivery"):
        result = dispatch(llm_output, hermes_home, relic_home, "test_subject")

    captured = capsys.readouterr()
    # Music delivered directly via Telegram Bot API — stdout must be empty
    assert captured.out == ""
    assert f"MEDIA:{fake_audio}" in captured.err
    assert result["tipo"] == "music"
