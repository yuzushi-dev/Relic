"""Minimal config shim for Relic OSS.

Reads configuration from environment variables.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any


class _Config:
    """Simple env-driven config object."""

    def __init__(self) -> None:
        self.data_dir = Path(os.environ.get("RELIC_DATA_DIR", "") or _default_data_dir())
        self.subject_id = os.environ.get("RELIC_SUBJECT_ID", "demo-subject")
        self.subject_name = os.environ.get("RELIC_SUBJECT_NAME", "Demo Subject")
        self.model = os.environ.get("RELIC_MODEL", "")
        self.provider = os.environ.get("RELIC_PROVIDER", "")
        self.hermes_bin = os.environ.get("HERMES_BIN", "hermes")
        self.relational_agent = os.environ.get("RELIC_RELATIONAL_AGENT", "")
        self.relational_agent_ids = [
            x.strip()
            for x in os.environ.get("RELIC_RELATIONAL_AGENT_IDS", self.relational_agent).split(",")
            if x.strip()
        ]

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


def _default_data_dir() -> str:
    hermes_home = os.environ.get("HERMES_HOME", os.environ.get("HOME", ""))
    return str(Path(hermes_home) / ".hermes" / "runtime" / "relic")


_CONFIG: _Config | None = None


def get_config() -> _Config:
    global _CONFIG
    if _CONFIG is None:
        _CONFIG = _Config()
    return _CONFIG


def load_nanobot_config(path: str | None = None) -> dict[str, Any]:
    """Return a minimal config dict from env vars."""
    cfg = get_config()
    return {
        "model": cfg.model,
        "provider": cfg.provider,
        "subject_id": cfg.subject_id,
        "subject_name": cfg.subject_name,
        "hermes_bin": cfg.hermes_bin,
        "data_dir": str(cfg.data_dir),
    }


def hermes_home() -> Path:
    home = os.environ.get("HERMES_HOME", os.environ.get("HOME", ""))
    return Path(home) / ".hermes"
