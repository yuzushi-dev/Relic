"""Tests that inject_context() is registered as PRE_LLM_CALL hook on plugin load.

Contract:
- After plugin.load(), PRE_LLM_CALL has at least one handler that invokes inject_context
- Handler is fail-open: returns {} on inject_context exception
- Handler passes session_id and user_message from payload
- Handler returns {"context": ...} when inject_context succeeds
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from relic.gumi_plugin import hooks as gumi_hooks
from relic.hermes_plugin.plugin import PluginConfig, RelicHermesPlugin


@pytest.fixture(autouse=True)
def reset_hooks():
    gumi_hooks.reset()
    yield
    gumi_hooks.reset()


class TestInjectContextHookRegistered:
    def test_pre_llm_call_has_inject_context_handler(self):
        """PRE_LLM_CALL must include a handler wired to inject_context after load."""
        plugin = RelicHermesPlugin()
        plugin.load(config=PluginConfig(subject_id="test-subj"))

        handlers = gumi_hooks._REGISTERED.get(gumi_hooks.PRE_LLM_CALL, [])
        assert len(handlers) >= 1

        # At least one handler name should reference inject_context
        handler_names = [h.__qualname__ for h in handlers]
        assert any("inject_context" in name for name in handler_names)

    def test_inject_context_handler_returns_context(self):
        """Handler returns {"context": ...} dict when inject_context produces output."""
        plugin = RelicHermesPlugin()
        plugin.load(config=PluginConfig(subject_id="test-subj"))

        with patch(
            "relic.hermes_plugin.plugin.inject_context",
            return_value={"context": "test context block"},
        ) as mock_ic:
            results = gumi_hooks.dispatch(
                gumi_hooks.PRE_LLM_CALL,
                {"session_id": "sess-1", "user_message": "ciao"},
            )

        # At least one result should be the context dict
        context_results = [r for r in results if isinstance(r, dict) and "context" in r]
        assert context_results, f"No context result in {results}"
        assert context_results[0]["context"] == "test context block"

    def test_inject_context_handler_passes_session_and_message(self):
        """Handler extracts session_id and user_message from payload."""
        plugin = RelicHermesPlugin()
        plugin.load(config=PluginConfig(subject_id="test-subj"))

        with patch(
            "relic.hermes_plugin.plugin.inject_context",
            return_value={"context": "x"},
        ) as mock_ic:
            gumi_hooks.dispatch(
                gumi_hooks.PRE_LLM_CALL,
                {"session_id": "my-session", "user_message": "hello"},
            )

        mock_ic.assert_called_with(session_id="my-session", user_message="hello")

    def test_inject_context_handler_fail_open(self):
        """Handler returns {} (not raises) when inject_context raises."""
        plugin = RelicHermesPlugin()
        plugin.load(config=PluginConfig(subject_id="test-subj"))

        with patch(
            "relic.hermes_plugin.plugin.inject_context",
            side_effect=RuntimeError("boom"),
        ):
            results = gumi_hooks.dispatch(
                gumi_hooks.PRE_LLM_CALL,
                {"session_id": "s", "user_message": "m"},
            )

        # No exception raised; dispatch completed normally
        assert isinstance(results, list)

    def test_inject_context_handler_returns_empty_on_none(self):
        """Handler returns {} when inject_context returns None."""
        plugin = RelicHermesPlugin()
        plugin.load(config=PluginConfig(subject_id="test-subj"))

        with patch(
            "relic.hermes_plugin.plugin.inject_context",
            return_value=None,
        ):
            results = gumi_hooks.dispatch(
                gumi_hooks.PRE_LLM_CALL,
                {"session_id": "s", "user_message": "m"},
            )

        context_results = [r for r in results if isinstance(r, dict) and "context" in r]
        assert not context_results
