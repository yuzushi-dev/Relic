"""Anti-repetition for prompt history — avoids duplicate messages.

Uses Jaccard similarity over word sets within a 24-hour window.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

ANTI_REPEAT_PATH = "state/prompt_history.json"
SIMILARITY_THRESHOLD = 0.55
HISTORY_WINDOW_HOURS = 24


def _history_path(hermes_home: Path) -> Path:
    return hermes_home / ANTI_REPEAT_PATH


def _tokenize(text: str) -> set[str]:
    """Simple whitespace tokenization, lowercased."""
    return set(text.lower().split())


def _jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard similarity: |intersection| / |union|."""
    if not a and not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union if union > 0 else 0.0


def load_history(hermes_home: Path) -> list[dict]:
    """Load prompt history, filtering out expired entries."""
    path = _history_path(hermes_home)
    if not path.exists():
        return []
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _save_history(hermes_home: Path, history: list[dict]) -> None:
    """Atomic write of prompt history."""
    path = _history_path(hermes_home)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def record_prompt(hermes_home: Path, text: str) -> None:
    """Add prompt text with timestamp, prune entries older than HISTORY_WINDOW_HOURS."""
    history = load_history(hermes_home)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=HISTORY_WINDOW_HOURS)

    # Remove expired entries
    history = [
        entry
        for entry in history
        if datetime.fromisoformat(entry["timestamp"]).replace(tzinfo=timezone.utc) > cutoff
    ]

    history.append({"text": text, "timestamp": datetime.now(timezone.utc).isoformat()})
    _save_history(hermes_home, history)


def is_duplicate(hermes_home: Path, candidate: str) -> bool:
    """Return True if candidate is too similar (>SIMILARITY_THRESHOLD) to any recent prompt."""
    history = load_history(hermes_home)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=HISTORY_WINDOW_HOURS)
    candidate_tokens = _tokenize(candidate)

    for entry in history:
        try:
            entry_time = datetime.fromisoformat(entry["timestamp"]).replace(tzinfo=timezone.utc)
            if entry_time < cutoff:
                continue
        except (ValueError, KeyError):
            continue

        entry_tokens = _tokenize(entry.get("text", ""))
        if _jaccard(candidate_tokens, entry_tokens) > SIMILARITY_THRESHOLD:
            return True

    return False


def suggest_placeholder(hermes_home: Path) -> str:
    """Placeholder suggestion — always returns empty string (caller decides to skip)."""
    return ""
