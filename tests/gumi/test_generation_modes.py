"""Tests for Gumi generation modes."""

import pytest
from relic.gumi.generation_modes import (
    GenerationModeRunner,
    GenerationReport,
)


@pytest.fixture
def subject_profile():
    """Sample subject profile for testing."""
    return {
        "subject_id": "test-subject-001",
        "occupation_or_study": "software_engineer",
        "location": "San Francisco",
        "family_structure": "single",
        "interests": ["coding", "music", "hiking"],
        "age_range": "25-35",
    }


@pytest.fixture
def runner():
    """Fresh runner instance for each test."""
    return GenerationModeRunner()


class TestReproducibility:
    """Test reproducibility of random generation."""

    def test_same_seed_produces_same_result(self, runner, subject_profile):
        """run_random with same seed produces identical final_candidate."""
        profile1, report1 = runner.run_random(subject_profile, seed=42)
        profile2, report2 = runner.run_random(subject_profile, seed=42)

        assert report1.final_candidate == report2.final_candidate

    def test_different_seed_produces_different_result(self, runner, subject_profile):
        """run_random with different seeds produces different results."""
        _, report1 = runner.run_random(subject_profile, seed=42)
        _, report2 = runner.run_random(subject_profile, seed=123)

        assert report1.final_candidate != report2.final_candidate


class TestManualMode:
    """Test manual generation mode."""

    def test_manual_provenance_for_all_fields(self, runner, subject_profile):
        """run_manual registers provenance='manual' for all fields."""
        field_values = {
            "identity": {"name": "John", "age": 30},
            "embodiment": {"height": "average"},
        }

        profile, report = runner.run_manual(subject_profile, field_values)

        assert all(
            p == "manual" for p in profile.provenance.values()
        ), "All fields should have provenance='manual'"

    def test_manual_sampled_fields_empty(self, runner, subject_profile):
        """run_manual has sampled_fields=[]."""
        field_values = {
            "identity": {"name": "John"},
        }

        _, report = runner.run_manual(subject_profile, field_values)

        assert report.sampled_fields == []


class TestHybridMode:
    """Test hybrid generation mode."""

    def test_hybrid_preserves_generated_and_final_values(self, runner, subject_profile):
        """run_hybrid preserves generated_value and final_value for override fields."""
        base_profile, _ = runner.run_random(subject_profile, seed=42)
        
        original_value = base_profile.domains.get("embodiment", {}).get("build", "default_build")
        researcher_overrides = {
            "embodiment_build": "athletic",
        }

        _, report = runner.run_hybrid(
            subject_profile, 
            seed=42, 
            researcher_overrides=researcher_overrides
        )

        assert f"embodiment_build_generated_value" in report.final_candidate
        assert f"embodiment_build_final_value" in report.final_candidate
        assert report.final_candidate["embodiment_build_final_value"] == "athletic"

    def test_hybrid_provenance_for_modified_fields(self, runner, subject_profile):
        """run_hybrid sets provenance='hybrid' for modified fields."""
        researcher_overrides = {
            "embodiment_build": "athletic",
        }

        profile, _ = runner.run_hybrid(
            subject_profile,
            seed=42,
            researcher_overrides=researcher_overrides,
        )

        assert profile.provenance.get("embodiment") == "hybrid"


class TestSweetSpotScore:
    """Test sweet spot score calculation."""

    def test_sweet_spot_score_in_range(self, runner, subject_profile):
        """compute_sweet_spot_score returns float in [0.0, 1.0]."""
        profile, report = runner.run_random(subject_profile, seed=42)

        assert 0.0 <= report.sweet_spot_score <= 1.0

    def test_sweet_spot_score_deterministic(self, runner, subject_profile):
        """Sweet spot score is deterministic for same inputs."""
        _, report1 = runner.run_random(subject_profile, seed=42)
        _, report2 = runner.run_random(subject_profile, seed=42)

        assert report1.sweet_spot_score == report2.sweet_spot_score


class TestRiskCheck:
    """Test risk flag detection."""

    def test_check_risk_detects_occupation_mirror(self, runner, subject_profile):
        """check_risk returns 'occupation_mirror' when occupation matches subject."""
        from relic.gumi.background_generator import GumiBackgroundProfile, GenerationMode

        profile = GumiBackgroundProfile(
            subject_id="test",
            generation_mode="random",
            profile_version=1,
            domains={
                "life_role": {"occupation_or_study": "software_engineer"},
                "identity": {},
                "embodiment": {},
                "place": {"location": "Different City"},
                "routine": {},
                "passions": {"primary_interests": [], "hobbies": []},
                "social_world": {
                    "friends": ["test"],
                    "family_kinship": ["test"],
                    "colleagues_contacts": ["test"],
                },
                "relationship_stance": {},
                "boundaries": {},
            },
            provenance={},
            anti_clone_checked=False,
            created_at="2024-01-01T00:00:00Z",
            random_seed=None,
        )

        flags = runner.check_risk(profile, subject_profile)

        assert "occupation_mirror" in flags

    def test_check_risk_detects_location_mirror(self, runner, subject_profile):
        """check_risk returns 'location_mirror' when location matches subject."""
        from relic.gumi.background_generator import GumiBackgroundProfile

        profile = GumiBackgroundProfile(
            subject_id="test",
            generation_mode="random",
            profile_version=1,
            domains={
                "life_role": {"occupation_or_study": "different_job"},
                "identity": {},
                "embodiment": {},
                "place": {"location": "San Francisco"},
                "routine": {},
                "passions": {"primary_interests": [], "hobbies": []},
                "social_world": {
                    "friends": ["test"],
                    "family_kinship": ["test"],
                    "colleagues_contacts": ["test"],
                },
                "relationship_stance": {},
                "boundaries": {},
            },
            provenance={},
            anti_clone_checked=False,
            created_at="2024-01-01T00:00:00Z",
            random_seed=None,
        )

        flags = runner.check_risk(profile, subject_profile)

        assert "location_mirror" in flags


class TestInputProfileHash:
    """Test deterministic input hash calculation."""

    def test_same_input_produces_same_hash(self, runner, subject_profile):
        """GenerationReport.input_profile_hash is deterministic."""
        _, report1 = runner.run_random(subject_profile, seed=1)
        _, report2 = runner.run_random(subject_profile, seed=2)

        assert report1.input_profile_hash == report2.input_profile_hash

    def test_different_input_produces_different_hash(self, runner):
        """Different inputs produce different hashes."""
        profile1 = {"subject_id": "A", "occupation": "dev"}
        profile2 = {"subject_id": "B", "occupation": "dev"}

        _, report1 = runner.run_random(profile1, seed=1)
        _, report2 = runner.run_random(profile2, seed=1)

        assert report1.input_profile_hash != report2.input_profile_hash
