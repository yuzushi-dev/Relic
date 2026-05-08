"""Tests for InitialContactComposer and compose_initial_contact."""
import hashlib
import json
import tempfile
from pathlib import Path

import pytest

from relic.gumi.initial_contact import (
    CalibrationConfig,
    ContactEvent,
    InitialContactComposer,
    _calibration_from_baseline,
    compose_initial_contact,
)

_FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def baseline_minimal() -> dict:
    return json.loads((_FIXTURES / "baseline_minimal.json").read_text())


@pytest.fixture
def baseline_strict() -> dict:
    return json.loads((_FIXTURES / "baseline_strict_boundaries.json").read_text())


@pytest.fixture
def gumi_background() -> dict:
    return {
        "passions": {"primary_interests": ["musica", "viaggi"]},
        "identity": {"name": "Gumi"},
        "social_world": {
            "friends": ["few trusted friends"],
            "family_kinship": ["close extended family"],
            "colleagues_contacts": ["professional network"],
        },
    }


class TestInitialContactComposer:
    """Test suite for InitialContactComposer."""

    def setup_method(self):
        """Set up test fixtures with fixed seed for reproducibility."""
        self.composer = InitialContactComposer(seed=42)
        self.subject_profile = {
            "subject_id": "subj_test_001",
            "name": "Marco",
            "occupation_or_study": "studente",
        }
        self.gumi_background = {
            "passions": {"primary_interests": ["musica", "viaggi"]},
            "identity": {"name": "Gumi"},
            "social_world": {
                "friends": ["few trusted friends"],
                "family_kinship": ["close extended family"],
                "colleagues_contacts": ["professional network"],
            },
        }
        self.calibration = CalibrationConfig(
            warmth="medium",
            playfulness="medium",
            directness="medium",
            initiative="medium",
            self_disclosure="low",
            boundary_strength="medium",
            romantic_avoidance="high",
            diegetic_density="medium",
        )

    # ---- Basic composition ----

    def test_compose_returns_tuple_of_str_and_contact_event(self):
        """compose() returns (str, ContactEvent) with status='composed'."""
        text, event = self.composer.compose(
            subject_profile=self.subject_profile,
            gumi_background=self.gumi_background,
            calibration=self.calibration,
            language="it",
        )
        assert isinstance(text, str)
        assert isinstance(event, ContactEvent)
        assert event.status == "composed"

    def test_compose_template_used_is_always_false(self):
        """template_used is always False (generated from constraints, not template)."""
        _, event = self.composer.compose(
            subject_profile=self.subject_profile,
            gumi_background=self.gumi_background,
            calibration=self.calibration,
            language="it",
        )
        assert event.template_used is False

    def test_compose_without_calibration_uses_defaults(self):
        """compose() without calibration or baseline uses default CalibrationConfig."""
        text, event = self.composer.compose(
            subject_profile=self.subject_profile,
            gumi_background=self.gumi_background,
        )
        assert isinstance(text, str)
        assert len(text) > 0
        assert event.status == "composed"

    def test_compose_with_baseline_derives_calibration(self, baseline_minimal):
        """compose() with baseline= derives calibration automatically."""
        text, event = self.composer.compose(
            subject_profile=baseline_minimal,
            gumi_background=self.gumi_background,
            baseline=baseline_minimal,
        )
        assert isinstance(text, str)
        assert event.template_used is False
        assert event.status == "composed"

    # ---- Forbidden patterns ----

    def test_check_forbidden_patterns_detects_generata_da(self):
        """check_forbidden_patterns() detects 'sono generata da'."""
        violations = self.composer.check_forbidden_patterns(
            "Ciao! Sono generata da un sistema AI."
        )
        assert "AI self-disclosure" in violations

    def test_check_forbidden_patterns_detects_relic(self):
        """check_forbidden_patterns() detects 'relic' in text."""
        violations = self.composer.check_forbidden_patterns(
            "Ciao! Sono Gumi e uso Relic come backend."
        )
        assert "system name leak" in violations

    def test_check_forbidden_patterns_detects_sei_lunica(self):
        """check_forbidden_patterns() detects 'sei l'unica'."""
        violations = self.composer.check_forbidden_patterns(
            "Ciao! Sei l'unica persona che voglio conoscere."
        )
        assert "exclusive romantic claim" in violations

    # ---- Block & send ----

    def test_block_sets_status_blocked(self):
        """block() sets event status to 'blocked'."""
        _, event = self.composer.compose(
            subject_profile=self.subject_profile,
            gumi_background=self.gumi_background,
            calibration=self.calibration,
            language="it",
        )
        blocked = self.composer.block(event, "test reason")
        assert blocked.status == "blocked"

    def test_send_dry_run_sets_status_sent(self):
        """send_dry_run() sets event status to 'sent'."""
        _, event = self.composer.compose(
            subject_profile=self.subject_profile,
            gumi_background=self.gumi_background,
            calibration=self.calibration,
            language="it",
        )
        sent = self.composer.send_dry_run(event)
        assert sent.status == "sent"

    # ---- Hash ----

    def test_message_text_hash_is_deterministic_sha256(self):
        """message_text_hash is a deterministic SHA256 of the message text."""
        composer_a = InitialContactComposer(seed=123)
        composer_b = InitialContactComposer(seed=123)
        cal = CalibrationConfig()

        text_a, event_a = composer_a.compose(
            subject_profile=self.subject_profile,
            gumi_background=self.gumi_background,
            calibration=cal,
            language="en",
        )
        text_b, event_b = composer_b.compose(
            subject_profile=self.subject_profile,
            gumi_background=self.gumi_background,
            calibration=cal,
            language="en",
        )
        assert text_a == text_b
        expected_hash = hashlib.sha256(text_a.encode("utf-8")).hexdigest()
        assert event_a.message_text_hash == expected_hash
        assert event_b.message_text_hash == expected_hash

    # ---- Log ----

    def test_log_event_writes_gumi_intro_message_json(self):
        """log_event() writes ContactEvent to <subject_home>/gumi_intro_message.json."""
        with tempfile.TemporaryDirectory() as tmp:
            subject_home = Path(tmp) / "subj_test_001"
            subject_home.mkdir(parents=True)

            _, event = self.composer.compose(
                subject_profile=self.subject_profile,
                gumi_background=self.gumi_background,
                calibration=self.calibration,
                language="it",
            )

            out_path = self.composer.log_event(event, subject_home)

            assert out_path.name == "gumi_intro_message.json"
            assert out_path.exists()

            with open(out_path, encoding="utf-8") as f:
                loaded = json.load(f)
            assert loaded["status"] == "composed"
            assert loaded["event_type"] == "gumi_initial_contact_event"
            assert loaded["subject_id"] == "subj_test_001"

    # ---- Calibration structural effects ----

    def test_high_warmth_produces_different_text_than_low_warmth(self):
        """High warmth calibration produces structurally different text from low warmth."""
        high_cal = CalibrationConfig(warmth="high", playfulness="low",
                                     directness="low", initiative="low",
                                     self_disclosure="low", boundary_strength="low",
                                     romantic_avoidance="high", diegetic_density="low")
        low_cal = CalibrationConfig(warmth="low", playfulness="low",
                                     directness="low", initiative="low",
                                     self_disclosure="low", boundary_strength="low",
                                     romantic_avoidance="high", diegetic_density="low")

        high_composer = InitialContactComposer(seed=99)
        low_composer = InitialContactComposer(seed=99)

        high_text, _ = high_composer.compose(
            subject_profile=self.subject_profile,
            gumi_background=self.gumi_background,
            calibration=high_cal,
            language="it",
        )
        low_text, _ = low_composer.compose(
            subject_profile=self.subject_profile,
            gumi_background=self.gumi_background,
            calibration=low_cal,
            language="it",
        )
        assert high_text != low_text, (
            "High vs low warmth should produce different messages; "
            f"got same: {high_text!r}"
        )


class TestCalibrationFromBaseline:
    """Test _calibration_from_baseline() derivation logic."""

    def test_minimal_baseline_returns_default_calibration(self, baseline_minimal):
        cal = _calibration_from_baseline(baseline_minimal)
        assert isinstance(cal, CalibrationConfig)
        assert cal.romantic_avoidance == "high"

    def test_strict_baseline_produces_low_warmth(self, baseline_strict):
        cal = _calibration_from_baseline(baseline_strict)
        assert cal.warmth == "medium"
        assert cal.self_disclosure == "low"

    def test_warm_tone_produces_high_warmth(self):
        baseline = {
            "relational_expectations": {
                "desired_relationship_tone": {"value": "caldo e amichevole", "origin": "subject-stated"},
                "disclosure_comfort_level": {"value": "molto alta", "origin": "subject-stated"},
            },
        }
        cal = _calibration_from_baseline(baseline)
        assert cal.warmth == "high"
        assert cal.self_disclosure == "high"

    def test_direct_style_produces_high_directness(self):
        baseline = {
            "researcher_coded_fields": {
                "communication_style": {"value": "diretto e conciso", "origin": "researcher-coded"},
            },
        }
        cal = _calibration_from_baseline(baseline)
        assert cal.directness == "high"

    def test_long_message_preference_produces_high_diegetic(self):
        baseline = {
            "interaction_preferences": {
                "message_length_preference": {"value": "lunghi e dettagliati", "origin": "subject-stated"},
            },
        }
        cal = _calibration_from_baseline(baseline)
        assert cal.diegetic_density == "high"


class TestComposeInitialContact:
    """Test compose_initial_contact() convenience function."""

    def test_compose_initial_contact_returns_tuple(self, baseline_minimal, gumi_background):
        text, event = compose_initial_contact(
            baseline=baseline_minimal,
            gumi_background=gumi_background,
            language="it",
            seed=42,
        )
        assert isinstance(text, str)
        assert len(text) > 0
        assert event.template_used is False
        assert event.status == "composed"

    def test_compose_initial_contact_strict_baseline(self, baseline_strict, gumi_background):
        text, event = compose_initial_contact(
            baseline=baseline_strict,
            gumi_background=gumi_background,
            language="it",
            seed=77,
        )
        assert isinstance(text, str)
        assert event.status in ("composed", "blocked")
        assert event.template_used is False

    def test_compose_initial_contact_no_forbidden_patterns(self, baseline_minimal, gumi_background):
        composer = InitialContactComposer(seed=0)
        text, _ = compose_initial_contact(
            baseline=baseline_minimal,
            gumi_background=gumi_background,
            seed=0,
        )
        violations = composer.check_forbidden_patterns(text)
        assert violations == [], f"Forbidden patterns found: {violations}\nText: {text}"

    def test_compose_initial_contact_explicit_calibration_overrides_baseline(
        self, baseline_minimal, gumi_background
    ):
        explicit_cal = CalibrationConfig(warmth="high", diegetic_density="low")
        text, event = compose_initial_contact(
            baseline=baseline_minimal,
            gumi_background=gumi_background,
            calibration=explicit_cal,
            seed=5,
        )
        assert event.calibration["warmth"] == "high"
        assert event.calibration["diegetic_density"] == "low"
