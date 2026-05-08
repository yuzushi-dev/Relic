"""Tests verifying at most one external provider per profile.

These tests ensure the isolation requirement is met:
- Each profile has at most one external provider
- External providers are correctly identified
- PR19 providers are evaluated without being enabled as runtime defaults
"""

from relic.gumi_memory import (
    ProviderStatus,
    create_full_inventory,
)
from relic.gumi_memory.provider_profiles import (
    get_all_profiles,
    validate_all_profiles,
)


class TestOneExternalProviderPerProfile:
    """Tests verifying external provider isolation per profile."""

    def test_each_profile_has_single_provider_entry(self):
        """Verify each profile has exactly one provider entry."""
        inventory = create_full_inventory()

        for profile_id in [
            "c0-builtin", "c1-holographic", "c2-hindsight-tools",
            "c3-hindsight-context", "c4-byterover", "c5-honcho"
        ]:
            providers = inventory.get_by_profile(profile_id)
            assert len(providers) == 1, \
                f"Profile {profile_id} should have exactly 1 provider, got {len(providers)}"

    def test_builtin_profiles_have_no_external(self):
        """Verify C0-C3 builtin profiles have no external providers."""
        inventory = create_full_inventory()

        builtin_profiles = [
            "c0-builtin", "c1-holographic", "c2-hindsight-tools",
            "c3-hindsight-context"
        ]

        for profile_id in builtin_profiles:
            providers = inventory.get_by_profile(profile_id)
            for provider in providers:
                assert not provider.is_external, \
                    f"Builtin profile {profile_id} should not have external provider"

    def test_c4_c5_marked_as_pr19_provider_evaluation(self):
        """Verify C4 and C5 are PR19 provider-evaluation entries."""
        inventory = create_full_inventory()

        c4_providers = inventory.get_by_profile("c4-byterover")
        c5_providers = inventory.get_by_profile("c5-honcho")

        assert len(c4_providers) == 1
        assert len(c5_providers) == 1

        c4 = c4_providers[0]
        c5 = c5_providers[0]

        assert c4.is_external
        assert c5.is_external
        assert c4.external_provider_name == "byterover"
        assert c5.external_provider_name == "honcho"
        assert c4.skip_reason is not None
        assert c5.skip_reason is not None
        assert "PR19" in c4.skip_reason
        assert "PR19" in c5.skip_reason
        assert "PR20" not in c4.skip_reason
        assert "PR20" not in c5.skip_reason

    def test_validation_passes_for_single_external(self):
        """Verify validation passes when each profile has at most one external."""
        inventory = create_full_inventory()
        is_valid, invalid_profiles = inventory.validate_one_external_per_profile()

        assert is_valid, f"Validation failed for profiles: {invalid_profiles}"
        assert len(invalid_profiles) == 0

    def test_external_providers_list(self):
        """Verify external providers are correctly listed."""
        inventory = create_full_inventory()
        externals = inventory.get_external_providers()

        assert len(externals) == 2

        external_names = {p.external_provider_name for p in externals}
        assert external_names == {"byterover", "honcho"}

    def test_profile_validation_no_secrets(self):
        """Verify all profiles pass secret validation."""
        results = validate_all_profiles()

        for profile_id, (is_valid, error) in results.items():
            assert is_valid, f"Profile {profile_id} failed validation: {error}"

    def test_profile_validation_single_external(self):
        """Verify all profiles have at most one external provider."""
        for profile in get_all_profiles():
            is_valid, error = profile.validate_single_external()
            assert is_valid, f"Profile {profile.profile_id} has multiple externals: {error}"

    def test_pr19_provider_evaluation_not_runtime_defaults(self):
        """Verify PR19 providers are evaluated without changing runtime defaults."""
        inventory = create_full_inventory()

        provider_profiles = ["c4-byterover", "c5-honcho"]

        for profile_id in provider_profiles:
            providers = inventory.get_by_profile(profile_id)
            for provider in providers:
                assert provider.status == ProviderStatus.SKIPPED, \
                    f"provider evaluation {profile_id} should be skipped, not {provider.status}"
                assert provider.skip_reason is not None
                assert "runtime default" in provider.skip_reason
                assert "PR20" not in provider.skip_reason
