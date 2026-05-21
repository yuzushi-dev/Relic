from __future__ import annotations

from pathlib import Path
from typing import Any


def install_relic_hermes_plugin(
    plugins_home: Path = Path.home() / ".hermes" / "plugins",
) -> dict[str, Any]:
    target = Path(__file__).resolve().parent / "hermes_entry"
    link_path = plugins_home / "relic"

    plugins_home.mkdir(parents=True, exist_ok=True)

    if link_path.is_symlink():
        resolved = link_path.resolve(strict=False)
        if resolved == target.resolve():
            return {
                "status": "already_installed",
                "link_path": str(link_path),
                "target_path": str(target),
            }
        return {
            "status": "conflict",
            "link_path": str(link_path),
            "target_path": str(target),
            "existing_target": str(resolved),
        }

    if link_path.exists():
        return {
            "status": "blocked",
            "link_path": str(link_path),
            "target_path": str(target),
        }

    link_path.symlink_to(target, target_is_directory=True)
    return {
        "status": "created",
        "link_path": str(link_path),
        "target_path": str(target),
    }
