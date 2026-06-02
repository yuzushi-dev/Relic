"""Tests for anti_repeat.py, Jaccard deduplication."""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from relic.gumi_plugin.anti_repeat import is_duplicate, record_prompt, suggest_placeholder


@pytest.fixture()
def hermes_home(tmp_path: Path) -> Path:
    return tmp_path / "hermes"


def test_same_text_is_duplicate(hermes_home: Path) -> None:
    text = "Ciao come stai oggi? Spero bene!"
    record_prompt(hermes_home, text)
    assert is_duplicate(hermes_home, text) is True


def test_different_text_not_duplicate(hermes_home: Path) -> None:
    record_prompt(hermes_home, "Buongiorno! Oggi ho lavorato molto.")
    assert is_duplicate(hermes_home, "Stasera guardo un film.") is False


def test_empty_history_not_duplicate(hermes_home: Path) -> None:
    assert is_duplicate(hermes_home, "Qualsiasi testo") is False


def test_suggest_placeholder_returns_string(hermes_home: Path) -> None:
    result = suggest_placeholder(hermes_home)
    assert isinstance(result, str)


def test_expired_entries_not_counted(hermes_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from relic.gumi_plugin import anti_repeat as ar

    text = "Vecchio messaggio di ieri"
    # Write entry with old timestamp directly
    from relic.gumi_plugin.anti_repeat import _history_path, _save_history
    old_ts = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
    _save_history(hermes_home, [{"text": text, "timestamp": old_ts}])
    assert is_duplicate(hermes_home, text) is False


def test_record_prunes_old_entries(hermes_home: Path) -> None:
    from relic.gumi_plugin.anti_repeat import _save_history, load_history
    from datetime import datetime, timedelta, timezone

    old_ts = (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat()
    _save_history(hermes_home, [{"text": "vecchio", "timestamp": old_ts}])
    record_prompt(hermes_home, "nuovo")
    history = load_history(hermes_home)
    assert all(h["text"] != "vecchio" for h in history)
