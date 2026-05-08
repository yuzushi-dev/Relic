"""Provider inventory for Hermes-native memory providers.

This module provides inventory capabilities for documenting memory providers
without runtime coupling. Outputs are compatibility reports only and cannot
change runtime defaults.
"""

from dataclasses import dataclass, field
from enum import Enum


class ProviderStatus(str, Enum):
    """Status of a memory provider."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SKIPPED = "skipped"
    ERROR = "error"


class ProviderType(str, Enum):
    """Type classification for memory providers."""
    BUILTIN = "builtin"
    EXTERNAL = "external"
    INTERNAL = "internal"
    PLUGIN = "plugin"


@dataclass
class ProviderInfo:
    """Information about a single memory provider."""
    name: str
    provider_type: ProviderType
    status: ProviderStatus
    profile: str
    is_external: bool = False
    external_provider_name: str | None = None
    skip_reason: str | None = None
    error_message: str | None = None
    redacted_path: str | None = None


@dataclass
class ProviderInventory:
    """Inventory report for all memory providers.

    This is a compatibility report only - it documents providers but does not
    modify runtime behavior.
    """
    providers: list[ProviderInfo] = field(default_factory=list)
    total_count: int = 0
    external_count: int = 0
    builtin_count: int = 0
    skipped_count: int = 0
    inventory_path: str | None = None

    def add_provider(self, provider: ProviderInfo) -> None:
        """Add a provider to the inventory."""
        self.providers.append(provider)
        self.total_count += 1
        if provider.is_external:
            self.external_count += 1
        if provider.provider_type == ProviderType.BUILTIN:
            self.builtin_count += 1
        if provider.status == ProviderStatus.SKIPPED:
            self.skipped_count += 1

    def get_by_profile(self, profile: str) -> list[ProviderInfo]:
        """Get providers for a specific profile."""
        return [p for p in self.providers if p.profile == profile]

    def get_external_providers(self) -> list[ProviderInfo]:
        """Get all external providers."""
        return [p for p in self.providers if p.is_external]

    def validate_one_external_per_profile(self) -> tuple[bool, list[str]]:
        """Validate that each profile has at most one external provider.

        Returns:
            Tuple of (is_valid, list of profiles with multiple externals)
        """
        profile_externals: dict[str, int] = {}
        for provider in self.providers:
            if provider.is_external:
                profile_externals[provider.profile] = (
                    profile_externals.get(provider.profile, 0) + 1
                )

        invalid_profiles = [
            profile for profile, count in profile_externals.items()
            if count > 1
        ]
        return len(invalid_profiles) == 0, invalid_profiles

    def to_dict(self) -> dict:
        """Convert inventory to dictionary for JSON serialization."""
        return {
            "providers": [
                {
                    "name": p.name,
                    "type": p.provider_type.value,
                    "status": p.status.value,
                    "profile": p.profile,
                    "is_external": p.is_external,
                    "external_provider_name": p.external_provider_name,
                    "skip_reason": p.skip_reason,
                    "error_message": p.error_message,
                    "redacted_path": p.redacted_path,
                }
                for p in self.providers
            ],
            "summary": {
                "total_count": self.total_count,
                "external_count": self.external_count,
                "builtin_count": self.builtin_count,
                "skipped_count": self.skipped_count,
            },
            "inventory_path": self.inventory_path,
        }


def create_c0_inventory() -> ProviderInventory:
    """Create inventory for C0 (builtin) profile."""
    inventory = ProviderInventory()
    inventory.add_provider(ProviderInfo(
        name="c0-builtin",
        provider_type=ProviderType.BUILTIN,
        status=ProviderStatus.ACTIVE,
        profile="c0-builtin",
        is_external=False,
        redacted_path="relic://c0-builtin/internal",
    ))
    return inventory


def create_c1_inventory() -> ProviderInventory:
    """Create inventory for C1 (holographic) profile."""
    inventory = ProviderInventory()
    inventory.add_provider(ProviderInfo(
        name="c1-holographic",
        provider_type=ProviderType.BUILTIN,
        status=ProviderStatus.ACTIVE,
        profile="c1-holographic",
        is_external=False,
        redacted_path="relic://c1-holographic/internal",
    ))
    return inventory


def create_c2_inventory() -> ProviderInventory:
    """Create inventory for C2 (hindsight-tools) profile."""
    inventory = ProviderInventory()
    inventory.add_provider(ProviderInfo(
        name="c2-hindsight-tools",
        provider_type=ProviderType.BUILTIN,
        status=ProviderStatus.ACTIVE,
        profile="c2-hindsight-tools",
        is_external=False,
        redacted_path="relic://c2-hindsight-tools/internal",
    ))
    return inventory


def create_c3_inventory() -> ProviderInventory:
    """Create inventory for C3 (hindsight-context) profile."""
    inventory = ProviderInventory()
    inventory.add_provider(ProviderInfo(
        name="c3-hindsight-context",
        provider_type=ProviderType.BUILTIN,
        status=ProviderStatus.ACTIVE,
        profile="c3-hindsight-context",
        is_external=False,
        redacted_path="relic://c3-hindsight-context/internal",
    ))
    return inventory


def create_c4_inventory() -> ProviderInventory:
    """Create inventory for C4 (byterover) profile."""
    inventory = ProviderInventory()
    inventory.add_provider(ProviderInfo(
        name="c4-byterover",
        provider_type=ProviderType.EXTERNAL,
        status=ProviderStatus.SKIPPED,
        profile="c4-byterover",
        is_external=True,
        external_provider_name="byterover",
        skip_reason="PR19 provider evaluation fixture only; live provider not enabled as runtime default",
        redacted_path="byterover://config",
    ))
    return inventory


def create_c5_inventory() -> ProviderInventory:
    """Create inventory for C5 (honcho) profile."""
    inventory = ProviderInventory()
    inventory.add_provider(ProviderInfo(
        name="c5-honcho",
        provider_type=ProviderType.EXTERNAL,
        status=ProviderStatus.SKIPPED,
        profile="c5-honcho",
        is_external=True,
        external_provider_name="honcho",
        skip_reason="PR19 provider evaluation fixture only; live provider not enabled as runtime default",
        redacted_path="honcho://config",
    ))
    return inventory


def create_full_inventory() -> ProviderInventory:
    """Create complete inventory across all C0-C5 profiles."""
    inventory = ProviderInventory()

    # C0-C3: builtin providers
    c0 = create_c0_inventory()
    c1 = create_c1_inventory()
    c2 = create_c2_inventory()
    c3 = create_c3_inventory()

    # C4-C5: PR19 providers represented as fixtures unless live profiles are configured.
    c4 = create_c4_inventory()
    c5 = create_c5_inventory()

    for prov in c0.providers + c1.providers + c2.providers + c3.providers:
        inventory.add_provider(prov)
    for prov in c4.providers + c5.providers:
        inventory.add_provider(prov)

    inventory.inventory_path = "artifacts/gumi-provider-eval/provider_inventory.json"
    return inventory
