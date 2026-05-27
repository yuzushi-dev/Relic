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

import io
import json

from relic.gumi_plugin.prose_critic import (
    ProseCritic,
    ProseVerdict,
    DEFAULT_THRESHOLD,
    log_calibration_sample,
    load_calibration_scores,
    suggest_threshold,
)


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

    def test_density_scored_by_occurrence(self) -> None:
        # More tells of the same kind → lower score (density, not mere presence).
        one = ProseCritic().review("In conclusione, è andata bene.")
        many = ProseCritic().review(
            "In conclusione, è importante notare che, in definitiva, vale la pena ricordare."
        )
        assert many.score < one.score

    def test_real_italian_slop_below_clean(self) -> None:
        slop = ProseCritic().review(
            "In conclusione, possiamo affermare che tale dinamica sia essenziale "
            "per navigare le complessità del panorama attuale."
        )
        clean = ProseCritic().review("Ehi, come è andata oggi?")
        assert slop.score < clean.score
        assert clean.score == 50

    def test_score_floors_at_zero(self) -> None:
        text = SLOP + " " + SLOP + " — — — non solo A ma anche B. La verità è che..."
        v = ProseCritic().review(text)
        assert v.score >= 0


class TestCalibration:
    def test_log_sample_is_numeric_only_no_text(self) -> None:
        sink = io.StringIO()
        secret = "questo testo segreto non deve mai finire nel log delle emozioni"
        v = ProseCritic().review(secret)
        log_calibration_sample(v, secret, decision_type="checkin", sink=sink)
        line = sink.getvalue().strip()
        rec = json.loads(line)
        # Privacy: raw text must never appear in the record.
        assert "segreto" not in line
        assert set(rec.keys()) == {
            "created_at", "score", "violations", "decision_type", "n_words", "gemma_score"
        }
        assert rec["decision_type"] == "checkin"
        assert rec["n_words"] == len(secret.split())

    def test_log_sample_fail_open(self) -> None:
        # Bad sink must not raise.
        class Boom:
            def write(self, _: str) -> None:
                raise RuntimeError("disk full")

        log_calibration_sample(ProseCritic().review("ciao"), "ciao", sink=Boom())

    def test_load_scores_from_jsonl(self, tmp_path) -> None:
        p = tmp_path / "cal.jsonl"
        p.write_text(
            "\n".join(json.dumps({"score": s, "violations": []}) for s in [50, 40, 30])
            + "\nNOT_JSON\n",  # malformed line ignored
            encoding="utf-8",
        )
        assert load_calibration_scores(p) == [50, 40, 30]

    def test_suggest_threshold_needs_min_samples(self) -> None:
        assert suggest_threshold([50] * 29) is None  # <30 → None

    def test_suggest_threshold_percentile(self) -> None:
        scores = list(range(1, 101))  # 1..100
        # 10th percentile, nearest-rank → 10
        assert suggest_threshold(scores, percentile=10.0) == 10
