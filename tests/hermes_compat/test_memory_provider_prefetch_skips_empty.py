"""FIX F: prefetch must skip empty markers instead of emitting [redacted]."""
from unittest.mock import MagicMock

from relic.hermes_plugin.memory_provider import RelicMemoryProvider


def _make_provider(markers):
    provider = RelicMemoryProvider(subject_id="s1")
    mock_store = MagicMock()
    mock_store.get_recent_markers.return_value = markers
    provider._store = mock_store
    return provider


def test_prefetch_skips_empty_markers_instead_of_redacting():
    markers = [
        {"subject_confirmation": True, "subject_words": []},
        {"subject_confirmation": True, "subject_words": ["hello"]},
    ]
    result = _make_provider(markers).prefetch("")
    assert result == "hello"
    assert "[redacted]" not in result


def test_prefetch_returns_empty_when_all_markers_empty():
    markers = [
        {"subject_confirmation": True, "subject_words": []},
        {"subject_confirmation": True, "subject_words": []},
    ]
    result = _make_provider(markers).prefetch("")
    assert result == ""
    assert "[redacted]" not in result


def test_prefetch_excludes_unconfirmed_markers():
    markers = [
        {"subject_confirmation": False, "subject_words": ["secret"]},
        {"subject_confirmation": True, "subject_words": ["visible"]},
    ]
    result = _make_provider(markers).prefetch("")
    assert result == "visible"
    assert "secret" not in result
