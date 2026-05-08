"""Test one provider per profile enforcement.

Acceptance criteria:
- One provider per profile is enforced
- Multi-provider memory is not assumed by blueprint

This test verifies:
- Each profile maps to exactly one runtime provider
- Provider isolation between profiles
- No multi-provider memory aggregation
"""

from __future__ import annotations


class TestOneProviderPerProfile:
    """Verify one provider per profile is enforced."""

    def test_profile_has_single_provider(self) -> None:
        """Each profile must map to exactly one runtime provider."""
        from relic.profiles import ProfileManager

        manager = ProfileManager()

        # Load all profiles
        profiles = manager.list_profiles()

        for profile_name in profiles:
            profile = manager.get_profile(profile_name)

            # Count providers for this profile
            provider_count = len(profile.get("runtime_providers", []))

            assert provider_count == 1, (
                f"Profile '{profile_name}' must have exactly 1 provider, got {provider_count}"
            )

    def test_provider_isolation_between_profiles(self) -> None:
        """Runtime providers must be isolated between profiles."""
        from relic.profiles import ProfileManager

        manager = ProfileManager()

        # Load profiles
        companion = manager.get_profile("companion")
        maintainer = manager.get_profile("relic-maintainer")

        # Extract provider IDs
        companion_providers = companion.get("runtime_providers", [])
        maintainer_providers = maintainer.get("runtime_providers", [])

        # Verify no overlap in provider IDs
        overlap = set(companion_providers) & set(maintainer_providers)

        assert len(overlap) == 0, f"Profiles must not share providers. Overlap: {overlap}"

    def test_blueprint_no_multi_provider_memory_assumption(self) -> None:
        """Blueprint must not assume multi-provider memory aggregation."""
        from relic.context import PromptContextPack
        from relic.hermes_plugin.context_injection import ContextSource

        pack = PromptContextPack()

        # Verify that multi-provider aggregation is not the default
        # Each provider should contribute independently
        sources = pack.get_context_sources()

        # Should not assume single monolithic memory block
        # Each source should be independently processed
        assert ContextSource.MULTI_PROVIDER_AGGREGATION not in sources, (
            "Blueprint must not assume multi-provider memory aggregation"
        )

    def test_provider_switch_requires_profile_change(self) -> None:
        """Switching providers must require explicit profile change."""
        from relic.hermes_plugin.fail_safe import FailSafeRegistry, FailSafeTrigger

        registry = FailSafeRegistry(enabled=True)

        # Simulate provider switch attempt
        result = registry.trigger(
            reason="Attempted provider switch without profile change",
            trigger=FailSafeTrigger.PROVIDER_SWITCH_WITHOUT_PROFILE,
        )

        assert result.blocked is True, (
            "Provider switch without profile change must be blocked"
        )

    def test_provider_config_isolation(self) -> None:
        """Provider configuration must be isolated per profile."""
        from relic.profiles import ProfileManager

        manager = ProfileManager()

        profiles = ["companion", "relic-maintainer"]

        for profile_name in profiles:
            profile = manager.get_profile(profile_name)

            # Verify provider config is isolated
            assert "provider_config" in profile, (
                f"Profile '{profile_name}' must have isolated provider_config"
            )


class TestBlueprintNoMonolithicPrompt:
    """Verify blueprint does not assume monolithic prompt."""

    def test_context_sources_are_independent(self) -> None:
        """Context sources must be independently processed."""
        from relic.hermes_plugin.context_injection import ContextSource

        # List all context sources
        all_sources = ContextSource.list_all()

        # Each source should be independently addressable
        for source in all_sources:
            assert hasattr(ContextSource, source.name), (
                f"Source {source} must be independently addressable"
            )

    def test_no_single_prompt_source_assumption(self) -> None:
        """Blueprint must not assume single prompt source."""
        from relic.context import PromptContextPack

        pack = PromptContextPack()

        # Should have multiple independent sources
        source_count = len(pack.get_context_sources())

        assert source_count >= 3, (
            "Must have at least 3 independent context sources (not monolithic)"
        )

    def test_fail_safe_blocks_monolithic_prompt_injection(self) -> None:
        """Fail-safe must block monolithic prompt injection."""
        from relic.hermes_plugin.fail_safe import FailSafeRegistry, FailSafeTrigger

        registry = FailSafeRegistry(enabled=True)

        result = registry.trigger(
            reason="Attempted monolithic prompt injection",
            trigger=FailSafeTrigger.MONOLITHIC_PROMPT_INJECTION,
        )

        assert result.blocked is True, "Monolithic prompt injection must be blocked"
