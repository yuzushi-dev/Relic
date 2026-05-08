"""Test that external memory candidates are not promoted as runtime providers."""
from relic.gumi_memory.provider_inventory import create_c0_inventory


def test_external_candidates_not_runtime_provider():
    """Verify external candidates are not marked as Hermes-native runtime providers."""
    inventory = create_c0_inventory()
    for provider in inventory.providers:
        if provider.skip_reason and "external candidate" in provider.skip_reason.lower():
            assert provider.status != "hermes-native", (
                f"External candidate {provider.provider_id} must not be a runtime provider"
            )
