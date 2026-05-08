"""Profile manager — one provider per profile enforcement."""

from __future__ import annotations

from typing import Any

_PROFILES: dict[str, dict[str, Any]] = {
    "companion": {
        "runtime_providers": ["companion-provider"],
        "provider_config": {"id": "companion-provider", "type": "local"},
    },
    "relic-maintainer": {
        "runtime_providers": ["maintainer-provider"],
        "provider_config": {"id": "maintainer-provider", "type": "local"},
    },
    "gumi": {
        "runtime_providers": ["gumi-provider"],
        "provider_config": {"id": "gumi-provider", "type": "local"},
    },
}


class ProfileManager:
    def list_profiles(self) -> list[str]:
        return list(_PROFILES.keys())

    def get_profile(self, name: str) -> dict[str, Any]:
        return _PROFILES.get(name, {
            "runtime_providers": [f"{name}-provider"],
            "provider_config": {"id": f"{name}-provider", "type": "local"},
        })
