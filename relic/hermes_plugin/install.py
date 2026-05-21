from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


PLUGIN_NAME = "relic"


def _plugin_entry_path() -> Path:
    return Path(__file__).resolve().parent / "hermes_entry"


def _plugin_link_path(hermes_home: Path) -> Path:
    return hermes_home / "plugins" / PLUGIN_NAME


def _config_path(hermes_home: Path) -> Path:
    return hermes_home / "config.yaml"


def install_relic_hermes_plugin(hermes_home: Path) -> dict[str, Any]:
    plugins_home = hermes_home / "plugins"
    target = _plugin_entry_path()
    link_path = _plugin_link_path(hermes_home)

    plugins_home.mkdir(parents=True, exist_ok=True)

    if link_path.is_symlink():
        resolved = link_path.resolve(strict=False)
        if resolved == target.resolve():
            return {
                "status": "already_installed",
                "hermes_home": str(hermes_home),
                "link_path": str(link_path),
                "target_path": str(target),
            }
        return {
            "status": "conflict",
            "hermes_home": str(hermes_home),
            "link_path": str(link_path),
            "target_path": str(target),
            "existing_target": str(resolved),
        }

    if link_path.exists():
        return {
            "status": "blocked",
            "hermes_home": str(hermes_home),
            "link_path": str(link_path),
            "target_path": str(target),
        }

    link_path.symlink_to(target, target_is_directory=True)
    return {
        "status": "created",
        "hermes_home": str(hermes_home),
        "link_path": str(link_path),
        "target_path": str(target),
    }


def enable_relic_hermes_plugin(hermes_home: Path) -> dict[str, Any]:
    """Enable the plugin in ``<hermes_home>/config.yaml``.

    Hermes' ``hermes plugins enable <name>`` command persists plugin state by
    updating ``plugins.enabled`` and removing the name from
    ``plugins.disabled`` in the active ``HERMES_HOME/config.yaml``.
    """

    config_path = _config_path(hermes_home)
    config_path.parent.mkdir(parents=True, exist_ok=True)

    if config_path.exists():
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        if config is None:
            config = {}
    else:
        config = {}

    if not isinstance(config, dict):
        raise ValueError(f"Expected mapping at {config_path}, found {type(config).__name__}")

    plugins = config.get("plugins")
    if not isinstance(plugins, dict):
        plugins = {}
        config["plugins"] = plugins

    enabled = plugins.get("enabled")
    enabled_list = sorted(set(enabled)) if isinstance(enabled, list) else []

    disabled = plugins.get("disabled")
    disabled_list = sorted(set(disabled)) if isinstance(disabled, list) else []

    already_enabled = PLUGIN_NAME in enabled_list and PLUGIN_NAME not in disabled_list
    if already_enabled:
        return {
            "status": "already_enabled",
            "hermes_home": str(hermes_home),
            "config_path": str(config_path),
            "enabled_plugins": enabled_list,
        }

    enabled_list = sorted(set(enabled_list) | {PLUGIN_NAME})
    disabled_list = sorted(set(disabled_list) - {PLUGIN_NAME})
    plugins["enabled"] = enabled_list
    plugins["disabled"] = disabled_list
    config_path.write_text(
        yaml.safe_dump(config, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return {
        "status": "enabled",
        "hermes_home": str(hermes_home),
        "config_path": str(config_path),
        "enabled_plugins": enabled_list,
    }
