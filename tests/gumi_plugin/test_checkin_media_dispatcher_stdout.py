"""Tests that checkin_media_dispatcher never leaks operator-facing text to stdout (I2).

Contract:
- voice dispatch: stdout empty regardless of api_key presence, Telegram failure, dry_run
- image dispatch: stdout empty (image + caption delivered directly via Telegram Bot API)
- music dispatch: stdout empty (music delivered directly via Telegram Bot API)
- dry_run any media type: stdout empty
- no_api_key any media type: stdout empty
- [WARN] lines: stderr only, never stdout
- [DRY-RUN] lines: stderr only, never stdout
- MEDIA: lines: stderr only, never stdout
- text dispatch: only sanitized testo on stdout (no WARN/DRY-RUN/MEDIA lines)
"""
from __future__ import annotations

import io
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from relic.gumi_plugin.checkin_media_dispatcher import dispatch


DUMMY_HOME = Path("/tmp/hermes_test")
DUMMY_SUBJECT_HOME = Path("/tmp/relic_test")


def _dispatch_capture(llm_output: str, dry_run: bool = False, **kwargs) -> tuple[str, str]:
    """Run dispatch(), return (stdout_captured, stderr_captured)."""
    out = io.StringIO()
    err = io.StringIO()
    with patch("sys.stdout", out), patch("sys.stderr", err):
        dispatch(
            llm_output=llm_output,
            hermes_home=DUMMY_HOME,
            relic_subject_home=DUMMY_SUBJECT_HOME,
            subject_id="test_subj",
            dry_run=dry_run,
            **kwargs,
        )
    return out.getvalue(), err.getvalue()


class TestVoiceStdout:
    def test_dry_run_stdout_empty(self):
        stdout, stderr = _dispatch_capture("tipo: voice\nMessaggio vocale.", dry_run=True)
        assert stdout == ""
        assert "[DRY-RUN]" in stderr

    def test_no_api_key_stdout_empty(self):
        with patch("relic.gumi_plugin.checkin_media_dispatcher._get_api_key", return_value=None):
            stdout, stderr = _dispatch_capture("tipo: voice\nMessaggio vocale.")
        assert stdout == ""
        assert "[WARN]" in stderr

    def test_delivered_stdout_empty(self):
        mock_audio = Path("/tmp/audio.ogg")
        with (
            patch("relic.gumi_plugin.checkin_media_dispatcher._get_api_key", return_value="key"),
            patch("relic.gumi_plugin.checkin_media_dispatcher.synthesize_checkin_audio", return_value=mock_audio),
            patch("relic.gumi_plugin.checkin_media_dispatcher.record_media_delivery"),
            patch("relic.gumi_plugin.checkin_media_dispatcher._send_telegram_media", return_value=True),
        ):
            stdout, stderr = _dispatch_capture("tipo: voice\nBuona notte.")
        assert stdout == ""
        assert "MEDIA:" in stderr

    def test_telegram_failure_stdout_empty(self):
        mock_audio = Path("/tmp/audio.ogg")
        with (
            patch("relic.gumi_plugin.checkin_media_dispatcher._get_api_key", return_value="key"),
            patch("relic.gumi_plugin.checkin_media_dispatcher.synthesize_checkin_audio", return_value=mock_audio),
            patch("relic.gumi_plugin.checkin_media_dispatcher.record_media_delivery"),
            patch("relic.gumi_plugin.checkin_media_dispatcher._send_telegram_media", return_value=False),
        ):
            stdout, stderr = _dispatch_capture("tipo: voice\nBuona notte.")
        assert stdout == ""


class TestImageStdout:
    def test_dry_run_stdout_empty(self):
        stdout, stderr = _dispatch_capture(
            "tipo: image\ncaption: Un fiore\nimage_prompt: a flower", dry_run=True
        )
        assert stdout == ""
        assert "[DRY-RUN]" in stderr

    def test_no_api_key_stdout_empty(self):
        with patch("relic.gumi_plugin.checkin_media_dispatcher._get_api_key", return_value=None):
            stdout, stderr = _dispatch_capture("tipo: image\ncaption: Un paesaggio")
        assert stdout == ""
        assert "[WARN]" in stderr

    def test_delivered_stdout_empty(self):
        mock_path = Path("/tmp/img.jpg")
        with (
            patch("relic.gumi_plugin.checkin_media_dispatcher._get_api_key", return_value="key"),
            patch("relic.gumi_plugin.checkin_media_dispatcher.generate_checkin_image", return_value=mock_path),
            patch("relic.gumi_plugin.checkin_media_dispatcher.record_media_delivery"),
            patch("relic.gumi_plugin.checkin_media_dispatcher._send_telegram_media", return_value=True),
        ):
            stdout, stderr = _dispatch_capture("tipo: image\ncaption: Cielo azzurro")
        assert stdout == ""
        assert "MEDIA:" in stderr


class TestMusicStdout:
    def test_dry_run_stdout_empty(self):
        stdout, stderr = _dispatch_capture("tipo: music\nUna melodia rilassante.", dry_run=True)
        assert stdout == ""
        assert "[DRY-RUN]" in stderr

    def test_no_api_key_stdout_empty(self):
        with patch("relic.gumi_plugin.checkin_media_dispatcher._get_api_key", return_value=None):
            stdout, stderr = _dispatch_capture("tipo: music\nPrompt musicale.")
        assert stdout == ""
        assert "[WARN]" in stderr

    def test_generation_failure_stdout_empty(self):
        mock_gen = MagicMock()
        mock_gen.generate_and_deliver.return_value = {"success": False, "reason": "quota"}
        with (
            patch("relic.gumi_plugin.checkin_media_dispatcher._get_api_key", return_value="key"),
            patch("relic.gumi_plugin.checkin_media_dispatcher.LyriaGenerator", return_value=mock_gen),
        ):
            stdout, stderr = _dispatch_capture("tipo: music\nBeat rilassante.")
        assert stdout == ""
        assert "[WARN]" in stderr

    def test_delivered_stdout_empty(self):
        mock_gen = MagicMock()
        mock_gen.generate_and_deliver.return_value = {
            "success": True, "audio_path": "/tmp/song.mp3", "caption": "Verse"
        }
        with (
            patch("relic.gumi_plugin.checkin_media_dispatcher._get_api_key", return_value="key"),
            patch("relic.gumi_plugin.checkin_media_dispatcher.LyriaGenerator", return_value=mock_gen),
            patch("relic.gumi_plugin.checkin_media_dispatcher.record_media_delivery"),
            patch("relic.gumi_plugin.checkin_media_dispatcher._send_telegram_media", return_value=True),
        ):
            stdout, stderr = _dispatch_capture("tipo: music\nBeat calmante.")
        assert stdout == ""
        assert "MEDIA:" in stderr


class TestTextSanitizer:
    def test_clean_text_passes_through(self):
        stdout, _ = _dispatch_capture("tipo: text\nBuongiorno! Come stai?")
        assert "Buongiorno!" in stdout

    def test_warn_line_in_llm_output_dropped(self):
        stdout, stderr = _dispatch_capture("tipo: text\n[WARN] qualcosa\nTesto pulito.")
        assert "[WARN]" not in stdout
        assert "Testo pulito" in stdout

    def test_fully_denied_text_produces_empty_stdout(self):
        stdout, stderr = _dispatch_capture("tipo: text\n[WARN] Missing token")
        assert stdout == ""

    def test_media_line_stripped_from_text(self):
        stdout, _ = _dispatch_capture("tipo: text\nMessaggio.\nMEDIA:/tmp/x.jpg")
        assert "MEDIA:" not in stdout
        assert "Messaggio" in stdout


class TestSendTelegramMediaWarnings:
    def test_missing_credentials_warn_on_stderr(self, tmp_path):
        """_send_telegram_media: missing bot_token/chat_id → [WARN] on stderr, not stdout."""
        from relic.gumi_plugin.checkin_media_dispatcher import _send_telegram_media
        dummy = tmp_path / "media.ogg"
        dummy.write_bytes(b"x")
        out = io.StringIO()
        err = io.StringIO()
        with patch("sys.stdout", out), patch("sys.stderr", err):
            # Empty hermes_home → no .env → no token/chat_id
            result = _send_telegram_media(tmp_path / "empty", dummy, "voice")
        assert result is False
        assert out.getvalue() == ""
        assert "[WARN]" in err.getvalue()

    def test_missing_media_file_warn_on_stderr(self, tmp_path):
        from relic.gumi_plugin.checkin_media_dispatcher import _send_telegram_media
        env_path = tmp_path / ".env"
        env_path.write_text("TELEGRAM_BOT_TOKEN=tok\nTELEGRAM_HOME_CHANNEL=123\n")
        out = io.StringIO()
        err = io.StringIO()
        with patch("sys.stdout", out), patch("sys.stderr", err):
            result = _send_telegram_media(tmp_path, tmp_path / "nonexistent.ogg", "voice")
        assert result is False
        assert out.getvalue() == ""
        assert "[WARN]" in err.getvalue()
