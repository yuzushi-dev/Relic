"""Tests for GumiBackgroundGenerator."""
from relic.gumi.background_generator import (
    GumiBackgroundGenerator,
    GumiBackgroundProfile,
    GenerationMode,
)


class TestGumiBackgroundGenerator:
    """Test suite for GumiBackgroundGenerator."""

    def setup_method(self):
        """Set up test fixtures."""
        self.generator = GumiBackgroundGenerator()
        self.subject_profile = {
            "subject_id": "test_subject_001",
            "occupation_or_study": "software_engineer",
            "location": "San Francisco, CA",
            "family_structure": "married with two children",
        }

    def test_generate_returns_profile_with_all_9_domains(self):
        """Test that generate() returns GumiBackgroundProfile with all 9 domain keys."""
        profile = self.generator.generate(
            subject_profile=self.subject_profile,
            mode=GenerationMode.RANDOM,
            seed=42,
        )
        assert isinstance(profile, GumiBackgroundProfile)
        assert len(profile.domains) == 9
        for domain in GumiBackgroundGenerator.REQUIRED_DOMAINS:
            assert domain in profile.domains, f"Missing domain: {domain}"

    def test_validate_returns_false_for_missing_domain(self):
        """Test that validate() returns False + errors for missing required domain."""
        profile = GumiBackgroundProfile(
            subject_id="test",
            generation_mode="random",
            profile_version=1,
            domains={"identity": {}},  # Missing other domains
            provenance={},
            anti_clone_checked=True,
            created_at="2026-01-01T00:00:00Z",
        )
        is_valid, errors = self.generator.validate(profile)
        assert is_valid is False
        assert len(errors) > 0
        assert any("Missing required domain" in e for e in errors)

    def test_validate_returns_false_for_missing_social_entries(self):
        """Test validate() fails when social_world is missing entries."""
        profile = GumiBackgroundProfile(
            subject_id="test",
            generation_mode="random",
            profile_version=1,
            domains={
                "identity": {}, "embodiment": {}, "place": {},
                "life_role": {}, "routine": {}, "passions": {},
                "social_world": {},  # Empty - no friends, family, colleagues
                "relationship_stance": {}, "boundaries": {},
            },
            provenance={},
            anti_clone_checked=True,
            created_at="2026-01-01T00:00:00Z",
        )
        is_valid, errors = self.generator.validate(profile)
        assert is_valid is False
        assert any("friend" in e.lower() for e in errors)
        assert any("family" in e.lower() for e in errors)
        assert any("colleague" in e.lower() for e in errors)

    def test_check_anti_clone_detects_exact_occupation_copy(self):
        """Test check_anti_clone() detects exact occupation copy."""
        profile = self.generator.generate(
            subject_profile=self.subject_profile,
            mode=GenerationMode.MANUAL,
            manual_overrides={
                "life_role": {"occupation_or_study": "software_engineer"}
            },
        )
        is_clean, violations = self.generator.check_anti_clone(
            profile, self.subject_profile
        )
        assert is_clean is False
        assert any("occupation" in v.lower() for v in violations)

    def test_check_anti_clone_detects_exact_location_copy(self):
        """Test check_anti_clone() detects exact location copy."""
        profile = self.generator.generate(
            subject_profile=self.subject_profile,
            mode=GenerationMode.MANUAL,
            manual_overrides={
                "place": {"location": "San Francisco, CA"}
            },
        )
        is_clean, violations = self.generator.check_anti_clone(
            profile, self.subject_profile
        )
        assert is_clean is False
        assert any("location" in v.lower() for v in violations)

    def test_check_anti_clone_detects_exact_family_structure_copy(self):
        """Test check_anti_clone() detects exact family_structure copy."""
        profile = self.generator.generate(
            subject_profile=self.subject_profile,
            mode=GenerationMode.MANUAL,
            manual_overrides={
                "identity": {"family_structure": "married with two children"}
            },
        )
        is_clean, violations = self.generator.check_anti_clone(
            profile, self.subject_profile
        )
        assert is_clean is False
        assert any("family_structure" in v.lower() for v in violations)

    def test_provenance_dict_records_source_for_each_domain(self):
        """Test provenance dict records source for each domain."""
        overrides = {"identity": {"name": "Test"}}
        profile = self.generator.generate(
            subject_profile=self.subject_profile,
            mode=GenerationMode.HYBRID,
            seed=100,
            manual_overrides=overrides,
        )
        assert len(profile.provenance) == 9
        assert profile.provenance["identity"] == "manual"
        # Generated/hybrid domains
        for domain in GumiBackgroundGenerator.REQUIRED_DOMAINS:
            assert domain in profile.provenance, f"Missing provenance for: {domain}"

    def test_social_world_has_minimum_entries(self):
        """Test social_world has minimum entries (friend, family, colleague)."""
        profile = self.generator.generate(
            subject_profile=self.subject_profile,
            mode=GenerationMode.RANDOM,
            seed=42,
        )
        social = profile.domains.get("social_world", {})
        assert "friends" in social and len(social["friends"]) >= 1
        assert "family_kinship" in social and len(social["family_kinship"]) >= 1
        assert "colleagues_contacts" in social and len(social["colleagues_contacts"]) >= 1

    def test_random_mode_with_same_seed_produces_identical_output(self):
        """Test RANDOM mode with same seed produces identical domain structure."""
        profile1 = self.generator.generate(
            subject_profile=self.subject_profile,
            mode=GenerationMode.RANDOM,
            seed=12345,
        )
        profile2 = self.generator.generate(
            subject_profile=self.subject_profile,
            mode=GenerationMode.RANDOM,
            seed=12345,
        )
        # Same domains
        assert set(profile1.domains.keys()) == set(profile2.domains.keys())
        # Same provenance
        assert profile1.provenance == profile2.provenance
        # Same random seed
        assert profile1.random_seed == profile2.random_seed == 12345

    def test_no_documentation_example_text_in_output(self):
        """Test no documentation example text appears verbatim in generated output."""
        forbidden_phrases = [
            "Mira, practical and dry-humored",
            "Enzo from the repair studio",
            "an older cousin who sends old music links",
        ]
        profile = self.generator.generate(
            subject_profile=self.subject_profile,
            mode=GenerationMode.RANDOM,
            seed=999,
        )
        profile_str = str(profile.domains)
        for phrase in forbidden_phrases:
            assert phrase not in profile_str, f"Forbidden phrase found: {phrase}"

    def test_manual_mode_records_provenance_as_manual(self):
        """Test MANUAL mode records provenance as 'manual' for overridden fields."""
        overrides = {
            "identity": {"name": "CustomName"},
            "passions": {"primary_interests": ["custom hobby"]},
        }
        profile = self.generator.generate(
            subject_profile=self.subject_profile,
            mode=GenerationMode.MANUAL,
            manual_overrides=overrides,
        )
        assert profile.provenance["identity"] == "manual"
        assert profile.provenance["passions"] == "manual"
        # Other domains in manual mode are empty with manual provenance
        assert profile.provenance["embodiment"] == "manual"

    def test_manual_mode_empty_domains_still_passes_validation(self):
        """Test MANUAL mode produces profile that validates (social minimum enforced)."""
        profile = self.generator.generate(
            subject_profile=self.subject_profile,
            mode=GenerationMode.MANUAL,
        )
        is_valid, errors = self.generator.validate(profile)
        # Should pass because social minimum is ensured
        assert is_valid is True
        assert len(errors) == 0

    def test_anti_clone_allows_different_values(self):
        """Test check_anti_clone() passes when values differ from baseline."""
        profile = self.generator.generate(
            subject_profile=self.subject_profile,
            mode=GenerationMode.RANDOM,
            seed=42,
        )
        is_clean, violations = self.generator.check_anti_clone(
            profile, self.subject_profile
        )
        # With random generation, values should differ from exact baseline
        assert is_clean is True
        assert len(violations) == 0


# Manual test runner
if __name__ == "__main__":
    import sys
    test_class = TestGumiBackgroundGenerator()
    passed = 0
    failed = 0
    
    for name in dir(test_class):
        if name.startswith('test_'):
            try:
                test_class.setup_method()
                getattr(test_class, name)()
                passed += 1
                print(f"✓ {name}")
            except AssertionError as e:
                failed += 1
                print(f"✗ {name}: {e}")
            except Exception as e:
                failed += 1
                print(f"✗ {name}: ERROR - {e}")
    
    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
