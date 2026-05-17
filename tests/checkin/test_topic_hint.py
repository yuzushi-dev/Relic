"""Tests for relic.checkin.topic_hint.

Specifies the contract for render_topic_hint(question_hint, recent_messages) -> str:
- Returns a formatted topic block, or "" if the hint is similar to recent messages
- Strips clinical scale references (ECR-R, DERS, SDT, ...)
- Never exposes facet_id or facet name
- Jaccard anti-repeat: if hint ≥ 0.85 similar to any recent message → ""
- Output passes RuntimePackSanitizer
- Token budget: ≤ 200 chars
"""
from __future__ import annotations

import pytest

from relic.checkin.topic_hint import render_topic_hint
from relic.patterns.runtime_pack_sanitizer import RuntimePackSanitizer, RuntimePack


# ---------------------------------------------------------------------------
# Basic rendering
# ---------------------------------------------------------------------------

class TestBasicRendering:
    def test_returns_block_for_fresh_hint(self):
        """Fresh hint with no recent messages → full block."""
        result = render_topic_hint(
            "Come gestisce le situazioni in cui deve chiedere aiuto. Spettro: indipendente ↔ chiede facilmente.",
            recent_messages=[],
        )
        assert result != ""
        assert "--- spunto di conversazione" in result

    def test_empty_hint_returns_empty(self):
        """Empty hint string → empty output."""
        assert render_topic_hint("", []) == ""

    def test_whitespace_only_hint_returns_empty(self):
        assert render_topic_hint("   ", []) == ""

    def test_block_header_present(self):
        result = render_topic_hint("Argomento di prova per il test.", [])
        assert result.startswith("--- spunto di conversazione"), \
            f"Expected header, got: {repr(result[:60])}"

    def test_hint_text_present_in_output(self):
        hint = "Come vive i periodi di cambiamento. Spettro: resistente ↔ adattabile."
        result = render_topic_hint(hint, [])
        assert "cambiamento" in result

    def test_output_ends_without_trailing_newlines(self):
        result = render_topic_hint("Argomento breve.", [])
        assert result == result.rstrip()


# ---------------------------------------------------------------------------
# Clinical scale reference stripping
# ---------------------------------------------------------------------------

class TestClinicalScaleStripping:
    def test_strips_ecr_r(self):
        hint = "Stile di attaccamento (ECR-R). Spettro: evitante ↔ sicuro."
        result = render_topic_hint(hint, [])
        assert "(ECR-R)" not in result
        assert "ECR-R" not in result

    def test_strips_ders(self):
        hint = "Regolazione emotiva (DERS). Spettro: disregolato ↔ regolato."
        result = render_topic_hint(hint, [])
        assert "DERS" not in result

    def test_strips_sdt(self):
        hint = "Motivazione autonoma (SDT). Spettro: estrinseca ↔ intrinseca."
        result = render_topic_hint(hint, [])
        assert "SDT" not in result
        assert "motivazione" in result.lower() or "spettro" in result.lower()

    def test_strips_multiple_refs(self):
        hint = "Autostima (RSE) e attaccamento (ECR-R). Spettro: bassa ↔ alta."
        result = render_topic_hint(hint, [])
        assert "RSE" not in result
        assert "ECR-R" not in result

    def test_content_preserved_after_strip(self):
        """Core description survives scale stripping."""
        hint = "Modalità di richiesta di aiuto (BSSS). Spettro: indipendente ↔ collaborativo."
        result = render_topic_hint(hint, [])
        assert "indipendente" in result or "collaborativo" in result


# ---------------------------------------------------------------------------
# Anti-repeat: Jaccard similarity gate
# ---------------------------------------------------------------------------

class TestAntiRepeat:
    def test_identical_hint_blocked(self):
        """Hint identical to a recent message → blocked (similarity = 1.0 ≥ 0.85)."""
        msg = "Come gestisce le situazioni in cui deve chiedere aiuto a qualcuno"
        result = render_topic_hint(msg, recent_messages=[msg])
        assert result == "", \
            f"Identical hint should be blocked, got: {repr(result)}"

    def test_highly_similar_hint_blocked(self):
        """Hint with high Jaccard similarity to recent message → blocked."""
        recent = "Come gestisce le situazioni in cui deve chiedere aiuto a qualcuno di vicino"
        hint   = "Come gestisce le situazioni in cui deve chiedere aiuto a qualcuno"
        result = render_topic_hint(hint, recent_messages=[recent])
        assert result == "", "Highly similar hint should be blocked"

    def test_dissimilar_hint_passes(self):
        """Hint with low similarity to recent messages → passes."""
        recent = ["Buongiorno, come stai oggi? Hai dormito bene stanotte?"]
        hint = "Come gestisce il cambiamento nelle routine quotidiane. Spettro: rigido ↔ flessibile."
        result = render_topic_hint(hint, recent_messages=recent)
        assert result != "", "Dissimilar hint should pass anti-repeat"

    def test_empty_recent_messages_always_passes(self):
        result = render_topic_hint("Argomento valido.", recent_messages=[])
        assert result != ""

    def test_multiple_recent_checked(self):
        """Anti-repeat checks against ALL recent messages, not just the last one."""
        # Second message shares 8/9 tokens with hint → Jaccard ≈ 0.89 ≥ 0.85
        hint   = "Come gestisce le situazioni in cui deve chiedere aiuto a qualcuno di vicino"
        recent = [
            "Stamattina il sole era bellissimo sul mare",
            "Come gestisce le situazioni in cui deve chiedere aiuto a qualcuno",
        ]
        result = render_topic_hint(hint, recent_messages=recent)
        assert result == "", "Should be blocked by second recent message"


# ---------------------------------------------------------------------------
# Sanitizer compliance
# ---------------------------------------------------------------------------

class TestSanitizerCompliance:
    FORBIDDEN_TERMS = [
        "psychological", "psicologico", "clinical", "clinico",
        "diagnosis", "diagnosi", "disorder", "syndrome",
        "ECR-R", "DERS", "SDT", "BSSS", "RSE",
    ]

    def test_sanitizer_passes_normal_output(self):
        hint = "Come vive i momenti di incertezza. Spettro: ansioso ↔ calmo."
        result = render_topic_hint(hint, [])
        if not result:
            return
        sanitizer = RuntimePackSanitizer()
        pack = RuntimePack("test_subj", "gumi-test", {"topic_hint": result})
        report = sanitizer.sanitize(pack)
        assert report.is_clean, \
            f"Sanitizer blocked topic hint: {report.blocked_terms} | {repr(result)}"

    def test_no_forbidden_terms_in_output(self):
        hint = "Stile di elaborazione cognitiva (ECR-R). Spettro: evitante ↔ sicuro."
        result = render_topic_hint(hint, [])
        result_lower = result.lower()
        for term in self.FORBIDDEN_TERMS:
            assert term.lower() not in result_lower, \
                f"Forbidden term '{term}' found in output: {repr(result)}"

    def test_disorder_in_hint_stripped_or_blocked(self):
        """If 'disorder' appears in hint (shouldn't happen via question_engine but defensive),
        output must not contain it."""
        hint = "Valutazione del disorder ansioso. Spettro: basso ↔ alto."
        result = render_topic_hint(hint, [])
        assert "disorder" not in result.lower()


# ---------------------------------------------------------------------------
# Token budget
# ---------------------------------------------------------------------------

class TestTokenBudget:
    def test_output_within_200_chars(self):
        """Topic hint block must fit within 200 chars."""
        hint = "Come gestisce le relazioni di lungo termine quando ci sono momenti di tensione. Spettro: evitante ↔ coinvolto."
        result = render_topic_hint(hint, [])
        assert len(result) <= 200, \
            f"Topic hint too long ({len(result)} chars): {repr(result)}"

    def test_long_hint_truncated_not_overflowing(self):
        """Very long hint is truncated to budget, not passed through as-is."""
        long_hint = "A" * 300
        result = render_topic_hint(long_hint, [])
        if result:
            assert len(result) <= 200


# ---------------------------------------------------------------------------
# Integration: topic + style combined output shows full checkin context
# ---------------------------------------------------------------------------

class TestCombinedOutput:
    """Shows what the final LLM user-turn context looks like end-to-end."""

    def test_combined_output_structure(self):
        """
        Simulates the full checkin stdout that Gumi receives.

        Recent messages → topic hint → style hints → avatar.
        This test documents the expected structure, not the implementation.
        """
        from relic.checkin.style_hints import render_style_hints

        recent_messages = [
            "[2026-05-16 09:30] Il sole sta appena iniziando a scaldare la costa mentre scrivo",
            "[2026-05-15 20:00] Il sole si sta posando dolce sui tetti qui, Daniele",
        ]
        recent_texts = [m.split("] ", 1)[1] if "] " in m else m for m in recent_messages]

        # Simulate what question_engine returns (sanitized hint, no scale refs)
        question_hint = "Come gestisce le situazioni in cui deve chiedere aiuto. Spettro: indipendente ↔ collaborativo."

        # Simulate interaction with enough confidence for one bullet
        interaction = {
            "emotional_intensity_tolerance": {"value": 0.10, "confidence_float": 0.50},
            "directness_preference":         {"value": 0.80, "confidence_float": 0.50},
        }

        topic_block = render_topic_hint(question_hint, recent_texts)
        style_block = render_style_hints(interaction)

        # Both blocks are non-empty in this case
        assert topic_block != "", "Topic block should be non-empty for fresh hint"
        assert style_block != "", "Style block should be non-empty with sufficient confidence"

        # Assemble full context (as cron_wiring.py would print to stdout)
        full_context = "\n".join(filter(None, [
            "--- messaggi recenti inviati (non ripetere immagini o temi già usati) ---",
            *[f"• {m}" for m in recent_messages],
            "",
            topic_block,
            "",
            style_block,
        ]))

        # Structural checks
        assert "--- spunto di conversazione" in full_context
        assert "--- come scriverle questo messaggio ---" in full_context
        assert "indipendente" in full_context or "collaborativo" in full_context
        assert "ECR-R" not in full_context
        assert "psychological" not in full_context.lower()

        # Token budget: total context addition ≤ 700 chars
        topic_style_len = len(topic_block) + len(style_block)
        assert topic_style_len <= 700, \
            f"Combined topic+style too long: {topic_style_len} chars"
