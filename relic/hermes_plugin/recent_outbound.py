"""Recent outbound surfacing for interactive continuity (BUGCHAT fix).

Proactive / check-in / diegetic messages are produced in isolated Hermes
``session_cron_*`` sessions. When the subject replies, the gateway opens a
*new* interactive session (``session_reset idle_minutes: 180``) that has no
record of the message Gumi just sent. The interactive model therefore answers
without knowing what it asked, it "is not conscious of previous messages".

This module scans the profile's own session store for the messages actually
delivered to the subject and renders them as a compact recent-conversation
block, injected at pre_llm_call time so the interactive turn is aware of its
own recent outbound.

Constraints:
- Read-only. Never writes to any session or memory file.
- Fail-open: any error returns an empty result so a turn is never blocked.
- Only subject-delivered messages are surfaced. Internal maintenance cron jobs
  (workspace compaction, continuity-candidate review) are excluded via
  is_maintenance_session(): those use workspace tools and their output is an
  audit report, not a message to the subject.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Lines emitted by the gate/composer scaffold that are not part of the
# subject-facing text. Dropped (or unwrapped) before surfacing.
_DROP_PREFIXES = ("tipo:", "image_prompt:", "ask:", "ask_topic:", "ora:", "deliver_context")
_UNWRAP_PREFIXES = ("caption:",)

# Cap how many recent session files we stat/parse: newest-first, bounded for
# perf on profiles with hundreds of cron sessions.
_MAX_SCAN_FILES = 40
_PER_MSG_CHARS = 240


def is_maintenance_session(data: dict[str, Any]) -> bool:
    """Return True for internal maintenance cron sessions (not subject-delivered).

    Maintenance jobs (world_state_compaction, continuity_candidate_review) read
    the workspace via tools and emit an audit report. Subject-facing delivery
    jobs (check-in / proactive / diegetic / media) never call tools, they emit
    plain text that the gateway delivers. The presence of any tool turn is a
    reliable discriminator.
    """
    for m in data.get("messages", []):
        if m.get("role") == "tool":
            return True
        if m.get("role") == "assistant" and m.get("tool_calls"):
            return True
    return False


def _clean_delivered_text(content: str) -> str:
    """Strip composer scaffold from a delivered message, returning subject text."""
    out: list[str] = []
    for line in str(content).splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        low = stripped.lower()
        if low.startswith(_DROP_PREFIXES):
            continue
        unwrapped = False
        for pref in _UNWRAP_PREFIXES:
            if low.startswith(pref):
                out.append(stripped[len(pref):].strip())
                unwrapped = True
                break
        if not unwrapped:
            out.append(stripped)
    text = " ".join(out).strip()
    if len(text) > _PER_MSG_CHARS:
        text = text[:_PER_MSG_CHARS].rstrip() + "…"
    return text


def _final_assistant_text(data: dict[str, Any]) -> str:
    """Return the last non-empty, non-[SILENT] assistant content in a session."""
    for m in reversed(data.get("messages", [])):
        if m.get("role") != "assistant":
            continue
        content = m.get("content") or ""
        if isinstance(content, list):
            content = " ".join(str(x) for x in content)
        content = str(content).strip()
        if not content or content == "[SILENT]":
            continue
        return content
    return ""


def recent_delivered_messages(
    hermes_home: Path,
    *,
    max_msgs: int = 3,
    within_hours: int = 48,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Return the most recent subject-delivered cron messages, newest first.

    Each item: {"ts": datetime, "text": str}. Empty list on any failure.
    """
    try:
        sessions_dir = Path(hermes_home) / "sessions"
        if not sessions_dir.is_dir():
            return []
        if now is None:
            now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=within_hours)

        files = sorted(
            sessions_dir.glob("session_cron_*.json"),
            key=lambda p: p.stat().st_mtime_ns,
            reverse=True,
        )[:_MAX_SCAN_FILES]

        out: list[dict[str, Any]] = []
        for path in files:
            try:
                mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            except OSError:
                continue
            if mtime < cutoff:
                break  # files are newest-first; everything older is out of window
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue
            if is_maintenance_session(data):
                continue
            raw = _final_assistant_text(data)
            if not raw:
                continue
            text = _clean_delivered_text(raw)
            if not text:
                continue
            out.append({"ts": mtime, "text": text})
            if len(out) >= max_msgs:
                break
        return out
    except Exception:
        logger.exception("recent_delivered_messages failed, returning empty")
        return []


def build_recent_outbound_context(
    hermes_home: Path,
    *,
    max_msgs: int = 3,
    within_hours: int = 48,
    now: datetime | None = None,
) -> str:
    """Render a compact 'messages you recently sent' block, or '' if none.

    The block is framed so the interactive model treats it as its own recent
    outbound, the subject's current turn may be a reply to one of these.
    """
    msgs = recent_delivered_messages(
        hermes_home, max_msgs=max_msgs, within_hours=within_hours, now=now
    )
    if not msgs:
        return ""
    lines = [
        "Messaggi recenti che hai inviato tu (Gumi) al soggetto. "
        "Il messaggio attuale del soggetto potrebbe essere una risposta a questi, "
        "tienine conto per restare coerente:"
    ]
    # Oldest-first reads more naturally as a short history.
    for m in reversed(msgs):
        ts = m["ts"]
        ts_str = ts.astimezone().strftime("%d/%m %H:%M") if isinstance(ts, datetime) else str(ts)
        lines.append(f"- [{ts_str}] {m['text']}")
    return "\n".join(lines)
