"""Tests for relic.checkin.style_hints.

Specifies the contract for render_style_hints(interaction) -> str:
- Accepts the `interaction` section of subject_baseline.json
- Returns a formatted block for the Gumi checkin prompt, or ""
- Never exposes raw facet keys, clinical terms, or numeric values
- Confidence floor: 0.20 (low_initial=0.10 → no bullet)
- Only negative-band items (≤0.35) generate bullets, except directness_preference
  which generates bullets at both ends (≥0.65 and ≤0.35)
- Returns "" when no bullet survives the filter
"""
from __future__ import annotations

import pytest

from relic.checkin.style_hints import render_style_hints
from relic.patterns.runtime_pack_sanitizer import RuntimePackSanitizer, RuntimePack


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _facet(value: float, confidence: str = "low_initial", confidence_float: float | None = None) -> dict:
    f = {"value": value, "confidence": confidence}
    if confidence_float is not None:
        f["confidence_float"] = confidence_float
    return f


FULL_LOW_INITIAL = {
    "ambiguity_tolerance":            _facet(1.0),
    "audio_tolerance":                _facet(0.5),
    "checkin_tolerance":              _facet(0.45),
    "critique_tolerance":             _facet(1.0),
    "directness_preference":          _facet(0.5),
    "emotional_intensity_tolerance":  _facet(0.167),
    "fictional_diegesis_tolerance":   _facet(0.45),
    "humor_tolerance":                _facet(1.0),
    "image_tolerance":                _facet(0.55),
    "music_tolerance":                _facet(0.5),
    "proactive_contact_tolerance":    _facet(0.45),
}


# ---------------------------------------------------------------------------
# Confidence floor — low_initial (0.10) never generates bullets
# ---------------------------------------------------------------------------

class TestConfidenceFloor:
    def test_all_low_initial_returns_empty(self):
        """daniele's real baseline: all low_initial → no bullets, empty string."""
        result = render_style_hints(FULL_LOW_INITIAL)
        assert result == "", f"Expected empty, got: {repr(result)}"

    def test_confidence_019_below_floor(self):
        """confidence_float=0.19 is below floor (0.20) → no bullet."""
        interaction = {
            "emotional_intensity_tolerance": _facet(0.10, confidence_float=0.19),
        }
        assert render_style_hints(interaction) == ""

    def test_confidence_020_at_floor(self):
        """confidence_float=0.20 is at the floor → bullet appears if value in range."""
        interaction = {
            "emotional_intensity_tolerance": _facet(0.10, confidence_float=0.20),
        }
        result = render_style_hints(interaction)
        assert result != "", "confidence_float=0.20 should produce a bullet"

    def test_confidence_string_low_maps_to_025(self):
        """confidence='low' → 0.25 → above floor → bullet for negative-band facet."""
        interaction = {
            "humor_tolerance": _facet(0.10, confidence="low"),
        }
        result = render_style_hints(interaction)
        assert result != ""

    def test_confidence_string_high_maps_to_080(self):
        """confidence='high' → 0.80 → well above floor."""
        interaction = {
            "emotional_intensity_tolerance": _facet(0.10, confidence="high"),
        }
        result = render_style_hints(interaction)
        assert result != ""


# ---------------------------------------------------------------------------
# Directness — bullets at both band extremes
# ---------------------------------------------------------------------------

class TestDirectnessPreference:
    def test_high_directness_generates_direct_bullet(self):
        """directness_preference ≥ 0.65 with confidence ≥ 0.20 → direct style bullet."""
        interaction = {"directness_preference": _facet(0.80, confidence_float=0.50)}
        result = render_style_hints(interaction)
        assert result != ""
        assert "diretto" in result.lower() or "preamboli" in result.lower(), \
            f"Expected direct style bullet, got: {repr(result)}"

    def test_low_directness_generates_soft_bullet(self):
        """directness_preference ≤ 0.35 with confidence ≥ 0.20 → soft/indirect style bullet."""
        interaction = {"directness_preference": _facet(0.20, confidence_float=0.50)}
        result = render_style_hints(interaction)
        assert result != ""
        assert "morbid" in result.lower() or "indirett" in result.lower(), \
            f"Expected soft style bullet, got: {repr(result)}"

    def test_neutral_directness_no_bullet(self):
        """directness_preference = 0.50 → neutral band → no bullet."""
        interaction = {"directness_preference": _facet(0.50, confidence_float=0.80)}
        result = render_style_hints(interaction)
        assert result == "", f"Neutral directness should produce no bullet, got: {repr(result)}"


# ---------------------------------------------------------------------------
# Negative-band-only facets (≤ 0.35 → bullet, > 0.35 → no bullet)
# ---------------------------------------------------------------------------

class TestNegativeBandFacets:
    @pytest.mark.parametrize("facet_key,value,expected_fragment", [
        ("humor_tolerance",              0.10, "battute"),
        ("emotional_intensity_tolerance", 0.10, "emotiv"),
        ("proactive_contact_tolerance",  0.10, "iniziativa"),
        ("fictional_diegesis_tolerance", 0.10, "concreto"),
    ])
    def test_low_value_generates_bullet(self, facet_key, value, expected_fragment):
        """Value ≤ 0.35 with sufficient confidence → bullet with expected Italian text."""
        interaction = {facet_key: _facet(value, confidence_float=0.50)}
        result = render_style_hints(interaction)
        assert result != ""
        assert expected_fragment in result.lower(), \
            f"{facet_key}={value} expected '{expected_fragment}' in output, got: {repr(result)}"

    @pytest.mark.parametrize("facet_key,value", [
        ("humor_tolerance",              0.80),
        ("emotional_intensity_tolerance", 0.70),
        ("proactive_contact_tolerance",  0.60),
        ("fictional_diegesis_tolerance", 0.60),
    ])
    def test_high_value_no_bullet(self, facet_key, value):
        """Value > 0.35 for negative-band facets → no bullet (high tolerance = no constraint)."""
        interaction = {facet_key: _facet(value, confidence_float=0.80)}
        result = render_style_hints(interaction)
        assert result == "", \
            f"{facet_key}={value} should produce no bullet, got: {repr(result)}"


# ---------------------------------------------------------------------------
# Non-whitelisted facets — never appear
# ---------------------------------------------------------------------------

class TestNonWhitelistedFacets:
    def test_psychological_section_not_accepted(self):
        """render_style_hints only accepts interaction dict — psychological keys ignored."""
        # Even if caller passes psychological keys, they must produce no output
        pseudo_interaction = {
            "agreeableness":      _facet(0.10, confidence_float=0.90),
            "attachment_anxiety": _facet(0.10, confidence_float=0.90),
            "conscientiousness":  _facet(0.10, confidence_float=0.90),
            "emotional_stability": _facet(0.10, confidence_float=0.90),
        }
        result = render_style_hints(pseudo_interaction)
        assert result == "", \
            f"Psychological keys should produce no output, got: {repr(result)}"

    def test_audio_image_music_tolerance_not_in_output(self):
        """audio_tolerance, image_tolerance, music_tolerance not whitelisted → no bullet."""
        interaction = {
            "audio_tolerance": _facet(0.05, confidence_float=0.90),
            "image_tolerance": _facet(0.05, confidence_float=0.90),
            "music_tolerance": _facet(0.05, confidence_float=0.90),
        }
        result = render_style_hints(interaction)
        assert result == "", \
            f"Non-whitelisted tolerance facets should be ignored, got: {repr(result)}"

    def test_checkin_tolerance_ambiguity_not_in_output(self):
        """checkin_tolerance and ambiguity_tolerance not in style whitelist."""
        interaction = {
            "checkin_tolerance":    _facet(0.05, confidence_float=0.90),
            "ambiguity_tolerance":  _facet(0.05, confidence_float=0.90),
            "critique_tolerance":   _facet(0.05, confidence_float=0.90),
        }
        result = render_style_hints(interaction)
        assert result == ""


# ---------------------------------------------------------------------------
# Clinical term guard — output must not contain forbidden terms
# ---------------------------------------------------------------------------

class TestClinicalTermGuard:
    FORBIDDEN = [
        "psychological", "psicologico", "facet", "tratto",
        "clinical", "clinico", "diagnosis", "diagnosi",
        "disorder", "syndrome", "score", "confidence",
        "0.", "1.", "0,", "1,",  # no raw numeric values
    ]

    def _make_high_conf_interaction(self) -> dict:
        return {
            "directness_preference":          _facet(0.80, confidence_float=0.80),
            "emotional_intensity_tolerance":  _facet(0.10, confidence_float=0.80),
            "humor_tolerance":                _facet(0.10, confidence_float=0.80),
            "proactive_contact_tolerance":    _facet(0.10, confidence_float=0.80),
            "fictional_diegesis_tolerance":   _facet(0.10, confidence_float=0.80),
        }

    def test_no_raw_facet_keys_in_output(self):
        result = render_style_hints(self._make_high_conf_interaction()).lower()
        for key in ["directness_preference", "humor_tolerance", "emotional_intensity_tolerance",
                    "proactive_contact_tolerance", "fictional_diegesis_tolerance"]:
            assert key not in result, f"Facet key '{key}' leaked into output"

    def test_no_forbidden_clinical_terms(self):
        result = render_style_hints(self._make_high_conf_interaction()).lower()
        for term in self.FORBIDDEN:
            assert term not in result, f"Forbidden term '{term}' found in output: {repr(result)}"

    def test_sanitizer_approves_output(self):
        """RuntimePackSanitizer must pass on the rendered output."""
        interaction = self._make_high_conf_interaction()
        result = render_style_hints(interaction)
        if not result:
            return  # empty is always clean
        sanitizer = RuntimePackSanitizer()
        pack = RuntimePack(
            subject_id="test_subj",
            gumi_instance_id="gumi-test",
            content={"style_hints": result},
        )
        report = sanitizer.sanitize(pack)
        assert report.is_clean, \
            f"Sanitizer blocked style hints output: {report.blocked_terms} | {repr(result)}"


# ---------------------------------------------------------------------------
# Output format contract
# ---------------------------------------------------------------------------

class TestOutputFormat:
    def test_block_header_present_when_non_empty(self):
        """Non-empty output starts with the section header."""
        interaction = {"directness_preference": _facet(0.80, confidence_float=0.80)}
        result = render_style_hints(interaction)
        assert result.startswith("--- come scriverle questo messaggio ---"), \
            f"Expected section header, got: {repr(result[:80])}"

    def test_bullets_use_dash_prefix(self):
        """Each directive is a '- ' prefixed line."""
        interaction = {
            "directness_preference":         _facet(0.80, confidence_float=0.80),
            "emotional_intensity_tolerance": _facet(0.10, confidence_float=0.80),
        }
        result = render_style_hints(interaction)
        lines = [l for l in result.splitlines() if l.strip() and not l.startswith("---")]
        assert all(l.startswith("- ") for l in lines), \
            f"All directive lines must start with '- ', got: {lines}"

    def test_output_is_italian(self):
        """Output contains Italian words (spot check)."""
        interaction = {"directness_preference": _facet(0.80, confidence_float=0.80)}
        result = render_style_hints(interaction)
        italian_words = ["lui", "preferisce", "messaggi", "evita", "mantieni", "stai"]
        assert any(w in result.lower() for w in italian_words), \
            f"Expected Italian output, got: {repr(result)}"

    def test_max_five_bullets(self):
        """At most 5 style bullets regardless of matching facets."""
        interaction = {
            "directness_preference":          _facet(0.80, confidence_float=0.90),
            "humor_tolerance":                _facet(0.10, confidence_float=0.90),
            "emotional_intensity_tolerance":  _facet(0.10, confidence_float=0.90),
            "proactive_contact_tolerance":    _facet(0.10, confidence_float=0.90),
            "fictional_diegesis_tolerance":   _facet(0.10, confidence_float=0.90),
            # extra: should not add a 6th bullet
            "ambiguity_tolerance":            _facet(0.10, confidence_float=0.90),
        }
        result = render_style_hints(interaction)
        bullet_lines = [l for l in result.splitlines() if l.startswith("- ")]
        assert len(bullet_lines) <= 5, \
            f"Expected ≤5 bullets, got {len(bullet_lines)}: {bullet_lines}"

    def test_token_budget(self):
        """Style block ≤ 400 chars (whitelist has max 5 bullets × ~80 chars)."""
        interaction = {
            "directness_preference":          _facet(0.80, confidence_float=0.90),
            "humor_tolerance":                _facet(0.10, confidence_float=0.90),
            "emotional_intensity_tolerance":  _facet(0.10, confidence_float=0.90),
            "proactive_contact_tolerance":    _facet(0.10, confidence_float=0.90),
            "fictional_diegesis_tolerance":   _facet(0.10, confidence_float=0.90),
        }
        result = render_style_hints(interaction)
        assert len(result) <= 400, \
            f"Style block too long ({len(result)} chars): {repr(result)}"


# ---------------------------------------------------------------------------
# Correction state guard
# ---------------------------------------------------------------------------

class TestCorrectionState:
    def test_corrected_facet_excluded(self):
        """A facet with correction_state='corrected' must not contribute a bullet."""
        interaction = {
            "humor_tolerance": {
                "value": 0.10,
                "confidence_float": 0.80,
                "correction_state": "corrected",
            }
        }
        result = render_style_hints(interaction)
        assert result == "", \
            f"Corrected facet should be excluded, got: {repr(result)}"

    def test_disputed_facet_excluded(self):
        interaction = {
            "proactive_contact_tolerance": {
                "value": 0.10,
                "confidence_float": 0.80,
                "correction_state": "disputed",
            }
        }
        assert render_style_hints(interaction) == ""

    def test_blocked_facet_excluded(self):
        interaction = {
            "emotional_intensity_tolerance": {
                "value": 0.05,
                "confidence_float": 0.90,
                "correction_state": "blocked",
            }
        }
        assert render_style_hints(interaction) == ""

    def test_active_state_included(self):
        """correction_state='active' (explicit) → facet counts normally."""
        interaction = {
            "humor_tolerance": {
                "value": 0.10,
                "confidence_float": 0.80,
                "correction_state": "active",
            }
        }
        result = render_style_hints(interaction)
        assert result != ""

    def test_missing_correction_state_defaults_to_active(self):
        """No correction_state field → treat as 'active' (defensive default)."""
        interaction = {
            "humor_tolerance": {"value": 0.10, "confidence_float": 0.80}
        }
        result = render_style_hints(interaction)
        assert result != ""
