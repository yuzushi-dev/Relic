"""Tests: ProseCritic scores AI writing tells and stays observe-only by default.

Contract:
- clean human prose → max score, allow=True, no violations
- banned phrases / structural tells reduce score and populate violations
- default posture never blocks (allow=True even below threshold)
- hard_block=True blocks only when score < threshold
- non-str / empty input fails open with max score
"""
from __future__ import annotations

import pytest

from relic.gumi_plugin.prose_critic import ProseCritic, ProseVerdict, DEFAULT_THRESHOLD


CLEAN = "Ehi, ho pensato a te oggi. Come è andata col progetto?"
SLOP = (
    "È importante notare che ci sono molti modi per navigare questo panorama "
    "— un viaggio nel mondo delle emozioni."
)


class TestProseCritic:
    def test_clean_prose_max_score(self) -> None:
        v = ProseCritic().review(CLEAN)
        assert v.allow is True
        assert v.score == 50
        assert v.reason == "ok"
        assert v.violations == []

    def test_slop_lowers_score_and_lists_violations(self) -> None:
        v = ProseCritic().review(SLOP)
        assert v.score < DEFAULT_THRESHOLD
        assert "throat_clearing" in v.violations
        assert "ai_cliche" in v.violations
        assert any(x.startswith("em_dash") for x in v.violations)

    def test_default_is_observe_only(self) -> None:
        # Even far below threshold, default posture never blocks.
        v = ProseCritic().review(SLOP)
        assert v.allow is True
        assert v.reason == "below_threshold"

    def test_hard_block_blocks_below_threshold(self) -> None:
        v = ProseCritic(hard_block=True).review(SLOP)
        assert v.allow is False

    def test_hard_block_allows_clean(self) -> None:
        v = ProseCritic(hard_block=True).review(CLEAN)
        assert v.allow is True

    def test_binary_contrast_detected(self) -> None:
        v = ProseCritic().review("Non solo ti capisco, ma anche ti sostengo.")
        assert "binary_contrast" in v.violations

    def test_rhetorical_setup_detected(self) -> None:
        v = ProseCritic().review("Ti sei mai chiesto perché succede?")
        assert "rhetorical_setup" in v.violations

    @pytest.mark.parametrize("bad", [None, "", "   ", 12345])
    def test_empty_or_nonstr_fails_open(self, bad: object) -> None:
        v = ProseCritic().review(bad)  # type: ignore[arg-type]
        assert isinstance(v, ProseVerdict)
        assert v.allow is True

    def test_english_tells_detected(self) -> None:
        text = ("It's worth noting that there are many ways to navigate this "
                "landscape — let's dive into the realm of emotions.")
        v = ProseCritic().review(text)
        assert v.score < DEFAULT_THRESHOLD
        assert "throat_clearing" in v.violations
        assert "ai_cliche" in v.violations
        assert "vague_declarative" in v.violations

    def test_english_binary_contrast(self) -> None:
        v = ProseCritic().review("Not only do I understand you, but also I support you.")
        assert "binary_contrast" in v.violations

    def test_english_rhetorical_setup(self) -> None:
        v = ProseCritic().review("Have you ever wondered why this happens?")
        assert "rhetorical_setup" in v.violations

    def test_score_floors_at_zero(self) -> None:
        text = SLOP + " " + SLOP + " — — — non solo A ma anche B. La verità è che..."
        v = ProseCritic().review(text)
        assert v.score >= 0
