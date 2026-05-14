"""Media delivery state tracking with cooldown enforcement.

Tracks last_image_ts, last_voice_ts, last_music_ts per profile.
Enforces minimum intervals between media of the same type.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

MEDIA_STATE_PATH = "state/media_delivery_state.json"

# Default cooldown days per media type
DEFAULT_COOLDOWN_DAYS = {"image": 2.0, "voice": 1.0, "music": 7.0}


def _media_state_path(hermes_home: Path) -> Path:
    return hermes_home / MEDIA_STATE_PATH


def load_media_state(hermes_home: Path) -> dict:
    """Load media state from JSON file. Returns empty dict if missing or corrupt."""
    path = _media_state_path(hermes_home)
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_media_state(hermes_home: Path, state: dict) -> None:
    """Atomic write: write to .tmp then rename to avoid corruption."""
    path = _media_state_path(hermes_home)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def last_media_ts(hermes_home: Path, media_type: str) -> Optional[datetime]:
    """Return last delivery timestamp for media_type, or None if never delivered."""
    state = load_media_state(hermes_home)
    ts_str = state.get(f"last_{media_type}_ts")
    if not ts_str:
        return None
    try:
        # Parse ISO format with timezone
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def record_media_delivery(hermes_home: Path, media_type: str) -> None:
    """Record current time as last delivery for media_type."""
    state = load_media_state(hermes_home)
    state[f"last_{media_type}_ts"] = datetime.now(timezone.utc).isoformat()
    save_media_state(hermes_home, state)


def is_media_eligible(
    hermes_home: Path,
    media_type: str,
    now: Optional[datetime] = None,
    cooldown_days: Optional[dict[str, float]] = None,
) -> bool:
    """Return True if media_type can be delivered (cooldown elapsed or never used)."""
    if cooldown_days is None:
        cooldown_days = DEFAULT_COOLDOWN_DAYS

    last_ts = last_media_ts(hermes_home, media_type)
    if last_ts is None:
        return True

    if now is None:
        now = datetime.now(timezone.utc)

    cooldown = cooldown_days.get(media_type, 2.0)
    elapsed = (now - last_ts).total_seconds() / 86400  # days
    return elapsed >= cooldown
