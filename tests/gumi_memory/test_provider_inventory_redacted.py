"""Tests for provider inventory with redaction verification.

These tests verify that the provider inventory:
- Contains no raw private memory content
- Reports C0-C5 profiles or explicit provider-evaluation skip reasons
- Uses only redacted paths
"""

import json

from relic.gumi_memory import (
    ProviderStatus,
    ProviderType,
    create_c0_inventory,
    create_c1_inventory,
    create_c2_inventory,
    create_c3_inventory,
    create_c4_inventory,
    create_c5_inventory,
    create_full_inventory,
)


class TestProviderInventoryRedacted:
    """Tests verifying inventory contains no raw private data."""

    def test_inventory_contains_no_raw_private_data(self):
        """Verify inventory output contains only names, status, counts, and redacted paths."""
        inventory = create_full_inventory()
        data = inventory.to_dict()

        # Check no raw private patterns
        forbidden_patterns = [
            "sk-", "API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY",
            "GEMINI_API_KEY", "honcho_api_key", "hindsight_token",
            "byterover_token", "raw_", "private_",
        ]

        json_str = json.dumps(data)
        for pattern in forbidden_patterns:
            assert pattern not in json_str, f"Forbidden pattern '{pattern}' found in inventory"

    def test_inventory_uses_only_redacted_paths(self):
        """Verify all provider paths are redacted (no file:// or absolute paths)."""
        inventory = create_full_inventory()

        for provider in inventory.providers:
            if provider.redacted_path:
                # Redacted paths should use scheme prefixes or be placeholder references
                assert not provider.redacted_path.startswith("/"), \
                    f"Provider {provider.name} has absolute path: {provider.redacted_path}"
                assert "home" not in provider.redacted_path.lower(), \
                    f"Provider {provider.name} has home path: {provider.redacted_path}"
                assert ".config" not in provider.redacted_path.lower(), \
                    f"Provider {provider.name} has config path: {provider.redacted_path}"

    def test_c0_inventory_is_builtin(self):
        """Verify C0 profile is builtin and active."""
        inventory = create_c0_inventory()
        assert len(inventory.providers) == 1

        provider = inventory.providers[0]
        assert provider.provider_type == ProviderType.BUILTIN
        assert provider.status == ProviderStatus.ACTIVE
        assert not provider.is_external

    def test_c1_inventory_is_builtin(self):
        """Verify C1 profile is builtin and active."""
        inventory = create_c1_inventory()
        assert len(inventory.providers) == 1

        provider = inventory.providers[0]
        assert provider.provider_type == ProviderType.BUILTIN
        assert provider.status == ProviderStatus.ACTIVE
        assert not provider.is_external

    def test_c2_inventory_is_builtin(self):
        """Verify C2 profile is builtin and active."""
        inventory = create_c2_inventory()
        assert len(inventory.providers) == 1

        provider = inventory.providers[0]
        assert provider.provider_type == ProviderType.BUILTIN
        assert provider.status == ProviderStatus.ACTIVE
        assert not provider.is_external

    def test_c3_inventory_is_builtin(self):
        """Verify C3 profile is builtin and active."""
        inventory = create_c3_inventory()
        assert len(inventory.providers) == 1

        provider = inventory.providers[0]
        assert provider.provider_type == ProviderType.BUILTIN
        assert provider.status == ProviderStatus.ACTIVE
        assert not provider.is_external

    def test_c4_inventory_has_provider_evaluation_skip_reason(self):
        """Verify C4 profile reports PR19 evaluation status with explicit skip reason."""
        inventory = create_c4_inventory()
        assert len(inventory.providers) == 1

        provider = inventory.providers[0]
        assert provider.status == ProviderStatus.SKIPPED
        assert provider.skip_reason is not None
        assert "PR19" in provider.skip_reason
        assert "runtime default" in provider.skip_reason
        assert "PR20" not in provider.skip_reason

    def test_c5_inventory_has_provider_evaluation_skip_reason(self):
        """Verify C5 profile reports PR19 evaluation status with explicit skip reason."""
        inventory = create_c5_inventory()
        assert len(inventory.providers) == 1

        provider = inventory.providers[0]
        assert provider.status == ProviderStatus.SKIPPED
        assert provider.skip_reason is not None
        assert "PR19" in provider.skip_reason
        assert "runtime default" in provider.skip_reason
        assert "PR20" not in provider.skip_reason

    def test_full_inventory_reports_c0_c5(self):
        """Verify full inventory reports all C0-C5 profiles."""
        inventory = create_full_inventory()

        profile_names = {p.profile for p in inventory.providers}
        expected_profiles = {
            "c0-builtin", "c1-holographic", "c2-hindsight-tools",
            "c3-hindsight-context", "c4-byterover", "c5-honcho"
        }

        assert profile_names == expected_profiles, \
            f"Expected profiles {expected_profiles}, got {profile_names}"

    def test_inventory_summary_counts(self):
        """Verify inventory summary counts are correct."""
        inventory = create_full_inventory()
        data = inventory.to_dict()
        summary = data["summary"]

        assert summary["total_count"] == 6
        assert summary["builtin_count"] == 4  # C0-C3
        assert summary["external_count"] == 2  # C4-C5 marked external
        assert summary["skipped_count"] == 2  # C4-C5 skipped

    def test_inventory_dict_serialization(self):
        """Verify inventory can be serialized to JSON-compatible dict."""
        inventory = create_full_inventory()
        data = inventory.to_dict()

        # Should not raise
        json_str = json.dumps(data)
        parsed = json.loads(json_str)

        assert "providers" in parsed
        assert "summary" in parsed
        assert len(parsed["providers"]) == 6
