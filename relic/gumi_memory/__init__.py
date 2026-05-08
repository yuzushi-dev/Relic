"""Gumi Memory Provider Inventory and Profile Management.

This module provides provider inventory and profile management for
Hermes-native memory configurations. Outputs are compatibility reports
only and cannot change runtime defaults.
"""

from relic.gumi_memory.provider_inventory import (
    ProviderInfo,
    ProviderInventory,
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
from relic.gumi_memory.provider_profiles import (
    PROFILE_DEFINITIONS,
    ProviderProfile,
    get_all_profiles,
    get_profile,
    validate_all_profiles,
)

__all__ = [
    "ProviderInfo",
    "ProviderInventory",
    "ProviderStatus",
    "ProviderType",
    "ProviderProfile",
    "PROFILE_DEFINITIONS",
    "create_c0_inventory",
    "create_c1_inventory",
    "create_c2_inventory",
    "create_c3_inventory",
    "create_c4_inventory",
    "create_c5_inventory",
    "create_full_inventory",
    "get_profile",
    "get_all_profiles",
    "validate_all_profiles",
]
