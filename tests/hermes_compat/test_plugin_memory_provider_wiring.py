"""Fix B: RelicMemoryProvider wired as pre/post_llm_call hooks in plugin.load()."""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from relic.gumi_plugin import hooks as gumi_hooks
from relic.hermes_plugin.plugin import PluginConfig, RelicHermesPlugin


def _make_plugin_with_subject(subject_id: str, hermes_profile_id: str = "") -> RelicHermesPlugin:
    plugin = RelicHermesPlugin()
    cfg = PluginConfig(subject_id=subject_id, hermes_profile_id=hermes_profile_id)
    plugin.load(config=cfg)
    return plugin


class TestMemoryProviderWiringViaConfig:
    def setup_method(self):
        gumi_hooks.reset()

    def teardown_method(self):
        gumi_hooks.reset()

    def test_pre_llm_call_registered_when_subject_id_set(self):
        with patch("relic.hermes_plugin.memory_provider.RelicMemoryProvider._get_store"):
            _make_plugin_with_subject("subj-001")
        assert gumi_hooks.PRE_LLM_CALL in gumi_hooks._REGISTERED
        assert len(gumi_hooks._REGISTERED[gumi_hooks.PRE_LLM_CALL]) >= 1

    def test_post_llm_call_memory_registered_when_subject_id_set(self):
        with patch("relic.hermes_plugin.memory_provider.RelicMemoryProvider._get_store"):
            _make_plugin_with_subject("subj-001")
        handlers = gumi_hooks._REGISTERED.get(gumi_hooks.POST_LLM_CALL, [])
        assert len(handlers) >= 2  # OutputCritic + memory

    def test_no_pre_llm_call_without_subject_id(self):
        plugin = RelicHermesPlugin()
        plugin.load(config=PluginConfig(subject_id=""))
        assert gumi_hooks._REGISTERED.get(gumi_hooks.PRE_LLM_CALL, []) == []

    def test_pre_llm_handler_returns_memory_context(self):
        mock_store = MagicMock()
        mock_store.get_recent_markers.return_value = [
            {"subject_confirmation": True, "subject_words": ["mi piace leggere"]}
        ]
        # Keep patch active through dispatch so _get_store() returns mock_store
        with patch("relic.hermes_plugin.memory_provider.RelicMemoryProvider._get_store", return_value=mock_store):
            _make_plugin_with_subject("subj-001")
            results = gumi_hooks.dispatch(gumi_hooks.PRE_LLM_CALL, {"query": "lettura"})

        memory_results = [r for r in results if r and "memory_context" in r]
        assert memory_results, "pre_llm_call must return memory_context when markers present"
        assert "mi piace leggere" in memory_results[0]["memory_context"]

    def test_pre_llm_handler_returns_empty_dict_on_no_markers(self):
        mock_store = MagicMock()
        mock_store.get_recent_markers.return_value = []
        with patch("relic.hermes_plugin.memory_provider.RelicMemoryProvider._get_store", return_value=mock_store):
            _make_plugin_with_subject("subj-002")
            results = gumi_hooks.dispatch(gumi_hooks.PRE_LLM_CALL, {"query": ""})

        # Handler must not inject noise — either empty dict or absent key
        for r in results:
            if r is not None:
                assert r.get("memory_context", "") == ""

    def test_post_llm_memory_handler_does_not_raise(self):
        with patch("relic.hermes_plugin.memory_provider.RelicMemoryProvider._get_store"):
            _make_plugin_with_subject("subj-003")
            # sync_turn is fire-and-forget; dispatch must not raise
            results = gumi_hooks.dispatch(
                gumi_hooks.POST_LLM_CALL,
                {"user_message": "ciao", "assistant_response": "salve"},
            )
        assert isinstance(results, list)


class TestMemoryProviderWiringViaEnv:
    def setup_method(self):
        gumi_hooks.reset()

    def teardown_method(self):
        gumi_hooks.reset()
        os.environ.pop("RELIC_SUBJECT_ID", None)

    def test_subject_id_sourced_from_env_when_config_empty(self):
        os.environ["RELIC_SUBJECT_ID"] = "env-subject-007"
        with patch("relic.hermes_plugin.memory_provider.RelicMemoryProvider._get_store"):
            plugin = RelicHermesPlugin()
            plugin.load(config=PluginConfig(subject_id=""))
        assert gumi_hooks._REGISTERED.get(gumi_hooks.PRE_LLM_CALL, []) != []

    def test_config_subject_id_takes_priority_over_env(self):
        os.environ["RELIC_SUBJECT_ID"] = "env-subject-007"
        captured = {}

        original_init = __import__(
            "relic.hermes_plugin.memory_provider", fromlist=["RelicMemoryProvider"]
        ).RelicMemoryProvider.__init__

        def patched_init(self, subject_id, **kwargs):
            captured["subject_id"] = subject_id
            original_init(self, subject_id=subject_id, **kwargs)

        with patch("relic.hermes_plugin.memory_provider.RelicMemoryProvider.__init__", patched_init):
            plugin = RelicHermesPlugin()
            plugin.load(config=PluginConfig(subject_id="config-subject-001"))

        assert captured.get("subject_id") == "config-subject-001"


class TestMemoryProviderSubjectGuard:
    def test_empty_subject_id_raises_on_direct_instantiation(self):
        from relic.hermes_plugin.memory_provider import RelicMemoryProvider
        with pytest.raises(ValueError, match="non-empty subject_id"):
            RelicMemoryProvider(subject_id="")

    def test_blank_subject_id_raises_on_direct_instantiation(self):
        from relic.hermes_plugin.memory_provider import RelicMemoryProvider
        with pytest.raises(ValueError, match="non-empty subject_id"):
            RelicMemoryProvider(subject_id="   ")
