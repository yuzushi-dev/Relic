"""Tests: delivery-time prose gate (_prose_block_reason) in checkin_media_dispatcher.

Contract:
- observe-only by default: returns None even on slop (never blocks delivery)
- opt-in via RELIC_PROSE_HARD_BLOCK: blocks below-threshold slop, allows clean
- fail-open on unexpected input
"""
from __future__ import annotations

import pytest

from relic.gumi_plugin.checkin_media_dispatcher import _prose_block_reason

SLOP = (
    "È importante notare che ci sono molti modi per navigare questo panorama "
    "— un viaggio nel mondo delle emozioni."
)
CLEAN = "Ehi, come è andata oggi?"


class TestProseGate:
    def test_observe_only_default_never_blocks(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("RELIC_PROSE_HARD_BLOCK", raising=False)
        assert _prose_block_reason(SLOP) is None
        assert _prose_block_reason(CLEAN) is None

    @pytest.mark.parametrize("flag", ["1", "true", "yes"])
    def test_hard_block_blocks_slop(self, monkeypatch: pytest.MonkeyPatch, flag: str) -> None:
        monkeypatch.setenv("RELIC_PROSE_HARD_BLOCK", flag)
        reason = _prose_block_reason(SLOP)
        assert reason is not None and reason.startswith("prose:")

    def test_hard_block_allows_clean(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RELIC_PROSE_HARD_BLOCK", "1")
        assert _prose_block_reason(CLEAN) is None

    def test_fail_open_on_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RELIC_PROSE_HARD_BLOCK", "1")
        assert _prose_block_reason("") is None
