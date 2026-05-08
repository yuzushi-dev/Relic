"""Plugin entrypoint and Hermes registration (PR22E)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class GumiPlugin:
    name: str = "relic-gumi"
    version: str = "0.1.0"
    enabled: bool = False
    config: dict[str, Any] = field(default_factory=dict)

    def is_ready(self) -> bool:
        return self.enabled and bool(self.config)

    def fail_closed(self) -> dict[str, Any]:
        """Returned when context-pack assembly fails. Hermes must inject nothing."""
        return {"context_pack": None, "reason": "fail_closed", "redacted": True}


def load_plugin(config_path: str | Path | None = None) -> GumiPlugin:
    if config_path is None:
        return GumiPlugin(enabled=False)
    p = Path(config_path)
    if not p.exists():
        return GumiPlugin(enabled=False)
    try:
        import yaml

        cfg = yaml.safe_load(p.read_text()) or {}
    except Exception:
        cfg = {}
    if not isinstance(cfg, dict):
        cfg = {}
    return GumiPlugin(enabled=True, config=cfg)
