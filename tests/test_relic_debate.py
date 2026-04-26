"""Tests for src/lib/relic_debate.py"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

DEBATE_MODULE = "lib.relic_debate"


@pytest.fixture()
def mock_chat(monkeypatch):
    """Mock chat_completion_content to return deterministic strings."""
    calls: list[dict] = []

    def _fake(model, messages, **kwargs):
        content = messages[0]["content"][:20]
        calls.append({"model": model, "content_preview": content})
        # Pro returns text, Contra returns text, Judge returns JSON
        if "Judge" in kwargs.get("title", ""):
            return (
                json.dumps(
                    {"verdict": "intervene_soft", "rationale": "test rationale", "confidence": 0.7}
                ),
                {},
            )
        return (f"Argument from {model}", {})

    monkeypatch.setattr(f"{DEBATE_MODULE}.chat_completion_content", _fake)
    return calls


def test_run_debate_returns_complete_dict(mock_chat):
    from lib.relic_debate import run_debate

    result = run_debate(
        domain="health",
        raw_data={"avg_confidence": 0.2},
        metrics={"coverage_pct": 0.3},
        report_text="Test report",
    )

    assert result["domain"] == "health"
    assert "pro" in result
    assert "contra" in result
    assert "judge" in result
    assert "generated_at" in result
    assert result["judge"]["verdict"] == "intervene_soft"
    assert result["judge"]["confidence"] == 0.7


def test_run_debate_all_domains_accepted(mock_chat):
    from lib.relic_debate import run_debate

    for domain in ("health", "humanness", "bio"):
        result = run_debate(domain=domain, raw_data={}, metrics={}, report_text="")
        assert result["domain"] == domain
        assert "error" not in result


def test_run_debate_uses_env_models(monkeypatch):
    monkeypatch.setenv("RELIC_INQUIRY_PRO_MODEL", "test/pro-model")
    monkeypatch.setenv("RELIC_INQUIRY_CONTRA_MODEL", "test/contra-model")
    monkeypatch.setenv("RELIC_INQUIRY_MODEL", "test/judge-model")

    used_models: list[str] = []

    def _fake(model, messages, **kwargs):
        used_models.append(model)
        if "Judge" in kwargs.get("title", ""):
            return (json.dumps({"verdict": "monitor", "rationale": "r", "confidence": 0.5}), {})
        return ("ok", {})

    monkeypatch.setattr(f"{DEBATE_MODULE}.chat_completion_content", _fake)

    from lib.relic_debate import run_debate

    run_debate(domain="health", raw_data={}, metrics={}, report_text="")
    assert "test/pro-model" in used_models
    assert "test/contra-model" in used_models
    assert "test/judge-model" in used_models


def test_run_debate_handles_judge_json_error(monkeypatch):
    def _fake(model, messages, **kwargs):
        return ("NOT VALID JSON {{{", {})

    monkeypatch.setattr(f"{DEBATE_MODULE}.chat_completion_content", _fake)

    from lib.relic_debate import run_debate

    result = run_debate(domain="health", raw_data={}, metrics={}, report_text="")
    # Should not raise; when all roles fail (non-JSON), heuristic verdict is returned
    assert result["judge"]["verdict"] in ("monitor", "intervene_soft")
    assert result["judge"]["confidence"] == 0.0
    assert result["judge"]["llm_available"] is False


def test_run_debate_domain_override_model(monkeypatch):
    """Per-domain override env var takes priority over shared RELIC_INQUIRY_PRO_MODEL."""
    monkeypatch.setenv("RELIC_INQUIRY_PRO_MODEL", "shared/pro")
    monkeypatch.setenv("RELIC_BIO_PRO_MODEL", "bio/pro-override")

    used_models: list[str] = []

    def _fake(model, messages, **kwargs):
        used_models.append(model)
        if "Judge" in kwargs.get("title", ""):
            return (json.dumps({"verdict": "monitor", "rationale": "r", "confidence": 0.5}), {})
        return ("ok", {})

    monkeypatch.setattr(f"{DEBATE_MODULE}.chat_completion_content", _fake)

    from lib.relic_debate import run_debate

    run_debate(domain="bio", raw_data={}, metrics={}, report_text="")
    assert "bio/pro-override" in used_models
    assert "shared/pro" not in used_models
