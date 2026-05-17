"""Tests for PRE_SEND sanitizer hook registered by RelicHermesPlugin.

Contract:
- PRE_SEND hook constant exists in gumi_hooks
- Plugin registers exactly one PRE_SEND handler on load (with subject_id)
- Handler returns {"action": "drop"} for [WARN] text
- Handler returns {"action": "drop"} for MEDIA: text
- Handler returns {"action": "drop"} for Traceback text
- Handler returns {"action": "deliver", "text": clean} for mixed content
- Handler returns {} (no-op) for clean text
- Handler is fail-open: exception returns {}
"""
from __future__ import annotations

import pytest

from relic.gumi_plugin import hooks as gumi_hooks
from relic.hermes_plugin.plugin import PluginConfig, RelicHermesPlugin


@pytest.fixture(autouse=True)
def reset_hooks():
    gumi_hooks.reset()
    yield
    gumi_hooks.reset()


def _load_plugin(subject_id: str = "test-subj") -> RelicHermesPlugin:
    plugin = RelicHermesPlugin()
    plugin.load(PluginConfig(subject_id=subject_id))
    return plugin


class TestPreSendHookExists:
    def test_pre_send_constant_in_gumi_hooks(self):
        assert hasattr(gumi_hooks, "PRE_SEND")
        assert gumi_hooks.PRE_SEND == "pre_send"

    def test_plugin_registers_pre_send_handler(self):
        _load_plugin()
        handlers = gumi_hooks._REGISTERED.get(gumi_hooks.PRE_SEND, [])
        assert len(handlers) >= 1

    def test_pre_send_registered_without_subject_id(self):
        """PRE_SEND is registered unconditionally (not gated on subject_id)."""
        plugin = RelicHermesPlugin()
        plugin.load(PluginConfig(subject_id=""))
        handlers = gumi_hooks._REGISTERED.get(gumi_hooks.PRE_SEND, [])
        assert len(handlers) >= 1


class TestPreSendHandlerBehavior:
    def _call_handler(self, text: str) -> dict:
        _load_plugin()
        handlers = gumi_hooks._REGISTERED.get(gumi_hooks.PRE_SEND, [])
        assert handlers, "No PRE_SEND handler registered"
        return handlers[-1]({"text": text})

    def test_warn_text_returns_drop(self):
        result = self._call_handler("[WARN] Missing token")
        assert result.get("action") == "drop"

    def test_media_text_returns_drop(self):
        result = self._call_handler("MEDIA:/tmp/audio.ogg [DELIVERED]")
        assert result.get("action") == "drop"

    def test_traceback_returns_drop(self):
        result = self._call_handler("Traceback (most recent call last):")
        assert result.get("action") == "drop"

    def test_error_line_returns_drop(self):
        result = self._call_handler("ERROR: something failed")
        assert result.get("action") == "drop"

    def test_clean_text_returns_empty_dict(self):
        result = self._call_handler("Buongiorno! Come stai?")
        assert result.get("action") != "drop"
        assert result.get("action") != "deliver"

    def test_mixed_content_returns_deliver_with_clean_text(self):
        result = self._call_handler("Buongiorno!\n[WARN] foo\nCome stai?")
        assert result.get("action") == "deliver"
        assert "[WARN]" not in result.get("text", "")
        assert "Buongiorno!" in result.get("text", "")

    def test_fail_open_on_exception(self):
        """Handler must not propagate exceptions — fail-open returns {}."""
        _load_plugin()
        handlers = gumi_hooks._REGISTERED.get(gumi_hooks.PRE_SEND, [])
        from unittest.mock import patch
        with patch(
            "relic.gumi_plugin.output_sanitizer.sanitize_for_subject",
            side_effect=RuntimeError("db error"),
        ):
            result = handlers[-1]({"text": "qualcosa"})
        assert result == {}
