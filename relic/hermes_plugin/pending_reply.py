"""Pending-reply tracking for capacity outages.

When a subject's message goes unanswered because the model had no inference
capacity (provider rate limit / transient infra failure), we record a marker so
the next generation that *does* have capacity can acknowledge the gap before
answering.

No hardcoded apology is ever sent to the subject: we only inject an
*instruction* into the model context, and only when the gap exceeds the
threshold. The model composes the acknowledgement itself, in character.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

# Acknowledge the delay only when the gap strictly exceeds 60 minutes. Below
# that the model just answers normally, with no acknowledgement.
ACK_THRESHOLD_SECONDS = 3600

_MARKER_NAME = "pending_reply.json"


def _marker_path(hermes_home) -> Path:
    return Path(hermes_home) / "state" / _MARKER_NAME


def is_capacity_error(text: str) -> bool:
    """True when ``text`` looks like a provider rate-limit / capacity failure."""
    if not text:
        return False
    t = text.lower()
    return (
        "429" in t
        or "rate limit" in t
        or "rate-limited" in t
        or "weekly usage limit" in t
        or "too many requests" in t
    )


def record_pending_reply(hermes_home, *, now: Optional[float] = None) -> None:
    """Mark that a reply is pending. Keeps the earliest failure timestamp."""
    try:
        path = _marker_path(hermes_home)
        if path.exists():
            return  # preserve the earliest first_failed_ts
        path.parent.mkdir(parents=True, exist_ok=True)
        ts = now if now is not None else time.time()
        path.write_text(json.dumps({"first_failed_ts": ts}), encoding="utf-8")
    except Exception:
        pass


def read_pending_reply(hermes_home) -> Optional[float]:
    """Return the earliest ``first_failed_ts`` if pending, else ``None``."""
    try:
        path = _marker_path(hermes_home)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8") or "{}")
        ts = data.get("first_failed_ts")
        return float(ts) if ts is not None else None
    except Exception:
        return None


def clear_pending_reply(hermes_home) -> None:
    """Remove the pending marker (a real reply was delivered)."""
    try:
        _marker_path(hermes_home).unlink(missing_ok=True)
    except Exception:
        pass


def pending_ack_instruction(hermes_home, *, now: Optional[float] = None) -> Optional[str]:
    """Context instruction acknowledging the delay, or ``None``.

    Returns ``None`` when nothing is pending or the gap does not exceed the
    threshold (answer normally). When the gap is long enough, returns an
    instruction telling the model to acknowledge the delay in character — the
    wording is left entirely to the model (no hardcoded message).
    """
    ts = read_pending_reply(hermes_home)
    if ts is None:
        return None
    elapsed = (now if now is not None else time.time()) - ts
    if elapsed <= ACK_THRESHOLD_SECONDS:
        return None

    minutes = int(elapsed // 60)
    if minutes >= 120:
        gap = f"circa {minutes // 60} ore"
    else:
        gap = f"circa {minutes} minuti"

    return (
        "[NOTA DI CONTINUITÀ — non mostrare questo testo al destinatario. "
        f"Non hai potuto rispondere all'ultimo messaggio per {gap} a causa di "
        "un problema tecnico temporaneo, ora risolto. Prima di rispondere nel "
        "merito, riconosci brevemente e in modo naturale il ritardo, nel tuo "
        "stile, senza menzionare dettagli tecnici.]"
    )


def resolve_hermes_home() -> Optional[Path]:
    """Best-effort resolution of the active profile home from the environment."""
    raw = os.environ.get("HERMES_HOME", "").strip()
    return Path(raw) if raw else None
