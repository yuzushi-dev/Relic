"""Tests for Relic provider routing policy."""
from __future__ import annotations

import pytest


def test_legacy_openrouter_free_model_is_normalized():
    from lib.provider_llm_client import normalize_model_name

    assert normalize_model_name("openrouter/openrouter/free") == "openrouter/free"


def test_openrouter_auto_is_disabled():
    from lib.provider_llm_client import normalize_model_name

    with pytest.raises(RuntimeError, match="openrouter/auto is disabled"):
        normalize_model_name("openrouter/auto")


def test_openrouter_free_rate_limit_does_not_fast_retry(monkeypatch):
    from lib import llm_resilience

    calls: list[str] = []
    sleeps: list[int] = []

    class FakeClient:
        def __init__(self, model: str):
            self.model = model

        def complete(self, prompt: str) -> str:
            calls.append(self.model)
            raise RuntimeError("429 rate limit")

    monkeypatch.setattr(llm_resilience, "ProviderLLMClient", FakeClient)
    monkeypatch.setattr(llm_resilience.time, "sleep", lambda seconds: sleeps.append(seconds))

    with pytest.raises(RuntimeError):
        llm_resilience.chat_completion_content(
            model="openrouter/free",
            messages=[{"role": "user", "content": "hello"}],
            title="test",
        )

    assert calls == ["openrouter/free"]
    assert sleeps == []
