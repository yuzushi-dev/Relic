"""Provider profile definitions for Hermes memory configurations.

This module defines provider profiles for different memory configurations.
Each profile demonstrates the provider setup but is example-only and
contains no secrets or raw memory content.
"""

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class ProviderProfile:
    """A memory provider profile configuration.

    Profile files are examples only and contain no secrets or raw memory content.
    Provider profile verification follows HERMES_BOOTSTRAP_CONTRACT.md.
    """
    profile_name: str
    profile_id: str
    provider_type: str
    is_external: bool
    config_path: Path
    description: str = ""
    external_provider_name: str | None = None
    skip_reason: str | None = None

    def validate_no_secrets(self) -> bool:
        """Validate that the profile contains no secrets."""
        if not self.config_path.exists():
            return True  # Non-existent files have no secrets

        content = self.config_path.read_text()

        # Check for forbidden patterns from LOCAL_PRIVATE_DATA_TEST_CONTRACT.md
        forbidden_patterns = [
            "API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY",
            "honcho_api_key", "hindsight_token", "byterover_token",
            "sk-", "sk1-", "sk2-",
        ]

        for pattern in forbidden_patterns:
            if pattern in content:
                return False
        return True

    def validate_single_external(self) -> tuple[bool, str]:
        """Validate that this profile has at most one external provider.

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self.config_path.exists():
            return True, ""

        try:
            with open(self.config_path) as f:
                config = yaml.safe_load(f)

            if config is None:
                return True, ""

            external_count = 0
            for key in config.keys():
                if key.startswith("external_") or key.endswith("_provider"):
                    external_count += 1

            return external_count <= 1, "" if external_count <= 1 else "Multiple external providers detected"
        except Exception as e:
            return False, f"Failed to parse config: {e}"


PROFILE_DEFINITIONS = {
    "c0-builtin": ProviderProfile(
        profile_name="C0 Builtin Memory",
        profile_id="gumi-c0-builtin",
        provider_type="builtin",
        is_external=False,
        config_path=Path("configs/hermes/profiles/gumi-c0-builtin.yaml"),
        description="Basic builtin memory without external providers",
    ),
    "c1-holographic": ProviderProfile(
        profile_name="C1 Holographic Memory",
        profile_id="gumi-c1-holographic",
        provider_type="builtin",
        is_external=False,
        config_path=Path("configs/hermes/profiles/gumi-c1-holographic.yaml"),
        description="Holographic memory representation",
    ),
    "c2-hindsight-tools": ProviderProfile(
        profile_name="C2 Hindsight Tools",
        profile_id="gumi-c2-hindsight-tools",
        provider_type="builtin",
        is_external=False,
        config_path=Path("configs/hermes/profiles/gumi-c2-hindsight-tools.yaml"),
        description="Hindsight tools integration",
    ),
    "c3-hindsight-context": ProviderProfile(
        profile_name="C3 Hindsight Context",
        profile_id="gumi-c3-hindsight-context",
        provider_type="builtin",
        is_external=False,
        config_path=Path("configs/hermes/profiles/gumi-c3-hindsight-context.yaml"),
        description="Hindsight context management",
    ),
    "c4-byterover": ProviderProfile(
        profile_name="C4 Byterover",
        profile_id="gumi-c4-byterover",
        provider_type="external",
        is_external=True,
        config_path=Path("configs/hermes/profiles/gumi-c4-byterover.yaml"),
        description="PR19 provider evaluation fixture",
        external_provider_name="byterover",
        skip_reason="PR19 provider evaluation fixture only; live provider not enabled as runtime default",
    ),
    "c5-honcho": ProviderProfile(
        profile_name="C5 Honcho",
        profile_id="gumi-c5-honcho",
        provider_type="external",
        is_external=True,
        config_path=Path("configs/hermes/profiles/gumi-c5-honcho.yaml"),
        description="PR19 provider evaluation fixture",
        external_provider_name="honcho",
        skip_reason="PR19 provider evaluation fixture only; live provider not enabled as runtime default",
    ),
}


def get_profile(profile_id: str) -> ProviderProfile | None:
    """Get a provider profile by ID."""
    return PROFILE_DEFINITIONS.get(profile_id)


def get_all_profiles() -> list[ProviderProfile]:
    """Get all provider profiles."""
    return list(PROFILE_DEFINITIONS.values())


def validate_all_profiles() -> dict[str, tuple[bool, str]]:
    """Validate all profiles for secrets and external count.

    Returns:
        Dict mapping profile_id to (is_valid, error_message)
    """
    results = {}
    for profile_id, profile in PROFILE_DEFINITIONS.items():
        secrets_ok = profile.validate_no_secrets()
        external_ok, external_msg = profile.validate_single_external()

        if secrets_ok and external_ok:
            results[profile_id] = (True, "")
        else:
            errors = []
            if not secrets_ok:
                errors.append("Contains secrets")
            if not external_ok:
                errors.append(external_msg)
            results[profile_id] = (False, "; ".join(errors))

    return results
