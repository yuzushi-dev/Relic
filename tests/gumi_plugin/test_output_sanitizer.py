"""Tests for output_sanitizer.sanitize_for_subject.

Contract (I3):
- Returns None for empty/whitespace-only input
- Returns None when ALL lines are operator-facing
- Drops [WARN] lines, keeps rest
- Drops [DRY-RUN] lines
- Drops [SILENT] lines
- Drops MEDIA: lines
- Drops Traceback lines
- Drops ERROR: lines
- Drops *Error: lines (e.g. ValueError:, RuntimeError:)
- Drops *Exception: lines
- Passes through clean text unchanged
- Mixed: returns stripped clean lines only
- Case-insensitive match on [warn] etc.
"""
from __future__ import annotations

import pytest

from relic.gumi_plugin.output_sanitizer import sanitize_for_subject


class TestDropPatterns:
    @pytest.mark.parametrize("text", [
        "[WARN] Missing TELEGRAM_BOT_TOKEN",
        "[WARN] Telegram delivery failed: timeout",
        "[warn] something",  # case-insensitive
        "[DRY-RUN] Voice synthesis skipped",
        "[DRY-RUN] Image generation skipped",
        "[SILENT]",
        "MEDIA:/tmp/audio.ogg [DELIVERED]",
        "MEDIA:/tmp/img.jpg [LOCAL_ONLY]",
        "Traceback (most recent call last):",
        "ERROR: subject_id required",
        "ValueError: invalid value",
        "RuntimeError: db unavailable",
        "KeyError: 'missing'",
        "AttributeError: foo",
        "ConnectionError: timeout",
        "ImportError: no module named x",
        "SomeException: exploded",
    ])
    def test_drops_single_deny_line(self, text: str):
        assert sanitize_for_subject(text) is None

    def test_empty_string_returns_none(self):
        assert sanitize_for_subject("") is None

    def test_whitespace_only_returns_none(self):
        assert sanitize_for_subject("   \n  \t  ") is None

    def test_none_equivalent_empty(self):
        assert sanitize_for_subject("") is None


class TestPassThrough:
    def test_clean_italian_text(self):
        text = "Ciao! Come stai oggi?"
        assert sanitize_for_subject(text) == text

    def test_multiline_clean_text(self):
        text = "Prima riga,\nSeconda riga!\nTerza riga?"
        assert sanitize_for_subject(text) == text

    def test_text_with_url(self):
        text = "Guarda questo: https://example.com"
        assert sanitize_for_subject(text) == text

    def test_strips_only_terminal_full_stop(self):
        assert sanitize_for_subject("Sto cucinando.") == "Sto cucinando"

    def test_strips_terminal_full_stop_before_emoji(self):
        assert sanitize_for_subject("Sto cucinando. ✨") == "Sto cucinando ✨"

    def test_keeps_question_exclamation_and_comma(self):
        text = "Ti va di raccontarmelo?\nGuarda che luce!\nresto qui,"
        assert sanitize_for_subject(text) == text


class TestMixedContent:
    def test_warn_mixed_with_clean_text(self):
        text = "Buongiorno!\n[WARN] Missing token\nCome stai?"
        result = sanitize_for_subject(text)
        assert result == "Buongiorno!\nCome stai?"

    def test_media_line_stripped_from_otherwise_valid(self):
        text = "Ecco la musica per te.\nMEDIA:/tmp/song.mp3 [DELIVERED]"
        result = sanitize_for_subject(text)
        assert result == "Ecco la musica per te"

    def test_multiple_warn_lines_all_dropped(self):
        text = "[WARN] line1\n[WARN] line2\nTesto pulito"
        result = sanitize_for_subject(text)
        assert result == "Testo pulito"

    def test_all_lines_operator_facing_returns_none(self):
        text = "[WARN] foo\n[DRY-RUN] bar\nMEDIA:/x"
        assert sanitize_for_subject(text) is None

    def test_traceback_block_dropped_line_by_line(self):
        text = "Ok.\nTraceback (most recent call last):\n  File foo.py\nValueError: bad\nFine."
        result = sanitize_for_subject(text)
        # Only "Ok" and "Fine" survive; indented traceback lines pass through
        # (only the Traceback header and ValueError: lines are denied)
        assert "Ok" in result
        assert "Fine" in result
        assert "Traceback" not in result
        assert "ValueError" not in result

    def test_result_stripped_of_leading_trailing_whitespace(self):
        text = "\n\nTesto\n\n"
        assert sanitize_for_subject(text) == "Testo"
