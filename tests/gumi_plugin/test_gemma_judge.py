"""Tests: gemma_judge.judge_score, parsing and fail-open behavior.

No real network: ollama calls are monkeypatched. Contract:
- parses an integer 0-100 from the model response, clamped
- returns None on empty/garbage response or any network error (fail-open)
- returns None for empty input without calling the model
"""
from __future__ import annotations

import io

import pytest

from relic.gumi_plugin import gemma_judge


def _fake_resp(payload: str):
    class _Ctx:
        def __enter__(self):
            return io.BytesIO(payload.encode())

        def __exit__(self, *a):
            return False

    return _Ctx()


class TestJudgeScore:
    def test_parses_score(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            gemma_judge.urllib.request, "urlopen",
            lambda *a, **k: _fake_resp('{"response": "73"}'),
        )
        assert gemma_judge.judge_score("ciao come va") == 73

    def test_clamps_out_of_range(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            gemma_judge.urllib.request, "urlopen",
            lambda *a, **k: _fake_resp('{"response": "150 punti"}'),
        )
        assert gemma_judge.judge_score("x y z") == 100

    def test_garbage_response_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            gemma_judge.urllib.request, "urlopen",
            lambda *a, **k: _fake_resp('{"response": "non lo so"}'),
        )
        assert gemma_judge.judge_score("x y z") is None

    def test_network_error_fail_open(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def boom(*a, **k):
            raise OSError("no network")

        monkeypatch.setattr(gemma_judge.urllib.request, "urlopen", boom)
        assert gemma_judge.judge_score("x y z") is None

    @pytest.mark.parametrize("bad", ["", "   ", None])
    def test_empty_input_no_call(self, bad, monkeypatch: pytest.MonkeyPatch) -> None:
        def boom(*a, **k):
            raise AssertionError("should not call model on empty input")

        monkeypatch.setattr(gemma_judge.urllib.request, "urlopen", boom)
        assert gemma_judge.judge_score(bad) is None  # type: ignore[arg-type]
