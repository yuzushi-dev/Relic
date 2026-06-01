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
OUTBOUND_STATE_PATH = "state/last_outbound.json"

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
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def _parse_iso(ts_str: Optional[str]) -> Optional[datetime]:
    if not ts_str:
        return None
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _lyria_last_generation(hermes_home: Path) -> Optional[datetime]:
    """Read LyriaGenerator's own cooldown timestamp (state/lyria_music_state.json).

    Kept as a direct file read (no import of lyria.py) to avoid coupling.
    """
    path = hermes_home / "state" / "lyria_music_state.json"
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return _parse_iso(data.get("last_generation"))
    except (json.JSONDecodeError, OSError):
        return None


def last_media_ts(hermes_home: Path, media_type: str) -> Optional[datetime]:
    """Return last delivery timestamp for media_type, or None if never delivered.

    For ``music`` the timestamp is unified with LyriaGenerator's own cooldown
    state (the later of the two). The gate (this module) and the generator
    previously tracked the music cooldown in separate files and could diverge,
    so the gate would select/force ``tipo: music`` that the generator then
    refused with "Cooldown active" — a silent non-delivery. Taking the max
    keeps both sides in agreement.
    """
    ts = _parse_iso(load_media_state(hermes_home).get(f"last_{media_type}_ts"))
    if media_type == "music":
        lyria_ts = _lyria_last_generation(hermes_home)
        if lyria_ts is not None and (ts is None or lyria_ts > ts):
            ts = lyria_ts
    return ts


def record_media_delivery(hermes_home: Path, media_type: str) -> None:
    """Record current time as last delivery for media_type."""
    state = load_media_state(hermes_home)
    state[f"last_{media_type}_ts"] = datetime.now(timezone.utc).isoformat()
    save_media_state(hermes_home, state)


def record_outbound_delivery(hermes_home: Path, channel: str, media_type: str) -> None:
    """Record outbound delivery timestamp/channel/media_type to state/last_outbound.json."""
    path = hermes_home / OUTBOUND_STATE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "last_outbound_ts": datetime.now(timezone.utc).isoformat(),
        "channel": channel,
        "media_type": media_type,
    }
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


_SENT_MEDIA_BEGIN = "<!-- gumi:sent_media:begin -->"
_SENT_MEDIA_END = "<!-- gumi:sent_media:end -->"


def record_sent_media_memory(
    hermes_home: Path,
    summary: str,
    *,
    timestamp: Optional[str] = None,
    max_entries: int = 8,
) -> None:
    """Append a first-person note of an outbound media to MEMORY.md.

    Media is delivered directly via the Telegram Bot API, outside the gateway
    conversation log, so the interactive agent would otherwise have no record
    that Gumi sent a photo / voice note / song. This keeps a small rolling,
    human-readable block in MEMORY.md (separate from the memory_sync block) so
    Gumi stays aware of what she just sent and does not get caught off guard if
    the subject replies to it. Best-effort: never raises.
    """
    try:
        mem_path = hermes_home / "MEMORY.md"
        ts = timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        new_line = f"- [{ts}] {summary}".strip()

        text = mem_path.read_text(encoding="utf-8") if mem_path.exists() else "# Memory Snapshot\n"

        begin_i = text.find(_SENT_MEDIA_BEGIN)
        end_i = text.find(_SENT_MEDIA_END)
        if begin_i != -1 and end_i != -1 and end_i > begin_i:
            inner = text[begin_i + len(_SENT_MEDIA_BEGIN):end_i]
            lines = [ln for ln in inner.splitlines() if ln.strip().startswith("- [")]
            lines.append(new_line)
            lines = lines[-max_entries:]
            block = (
                _SENT_MEDIA_BEGIN
                + "\n## Cose che ho inviato di recente\n"
                + "\n".join(lines)
                + "\n"
                + _SENT_MEDIA_END
            )
            text = text[:begin_i] + block + text[end_i + len(_SENT_MEDIA_END):]
        else:
            block = (
                _SENT_MEDIA_BEGIN
                + "\n## Cose che ho inviato di recente\n"
                + new_line
                + "\n"
                + _SENT_MEDIA_END
            )
            text = text.rstrip() + "\n\n" + block + "\n"

        tmp = mem_path.with_suffix(".md.tmp")
        tmp.write_text(text, encoding="utf-8")
        # Subject PII in clear text: restrict to owner-only before the rename
        # (os.replace preserves the tmp file's mode on the final path).
        os.chmod(tmp, 0o600)
        os.replace(tmp, mem_path)
    except Exception:
        pass


def last_outbound_ts(hermes_home: Path) -> Optional[datetime]:
    """Return last outbound delivery timestamp as tz-aware UTC datetime, or None."""
    path = hermes_home / OUTBOUND_STATE_PATH
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        ts_str = data.get("last_outbound_ts")
        if not ts_str:
            return None
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (json.JSONDecodeError, OSError, ValueError, TypeError):
        return None


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
