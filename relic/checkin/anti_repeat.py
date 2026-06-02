"""Anti-repeat gate for check-in question generation.

Two mechanisms (ported from backup anti_repeat.py):
1. Jaccard similarity on word n-grams, blocks if > threshold (default 0.85)
2. Archetype cooldown, limits reuse of tonal archetypes within 24h

Usage:
    from relic.checkin.anti_repeat import AntiRepeatGate
    gate = AntiRepeatGate(db_path)
    result = gate.check(candidate_text)
    if result["duplicate"]:
        # use fallback message
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# Minimum Jaccard similarity to trigger block
JACCARD_THRESHOLD = 0.85

# Tonal archetypes and their max uses per 24h
ARCHETYPE_PATTERNS: dict[str, list[str]] = {
    "leggerezza":  ["facile", "leggero", "semplice", "veloce", "piccolo", "breve"],
    "ondate":      ["senti", "percepisci", "noti", "hai visto", "ti colpisce"],
    "movimento":   ["vai", "muovi", "cambia", "provi", "salti", "corri"],
    "ridicolo":    ["assurdo", "ridicolo", "strano", "bizzarro", "folle"],
}
ARCHETYPE_MAX_PER_DAY = 2


def _tokenize(text: str) -> set[str]:
    """Split text into lowercase word tokens, strip punctuation."""
    return set(re.findall(r"\b\w{3,}\b", text.lower()))


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def _detect_archetypes(text: str) -> list[str]:
    text_lower = text.lower()
    found = []
    for name, keywords in ARCHETYPE_PATTERNS.items():
        if any(kw in text_lower for kw in keywords):
            found.append(name)
    return found


# SQL to persist recent questions: reuses checkin_exchanges from relic.db
_RECENT_Q_SQL = """
    SELECT question_text, asked_at
    FROM checkin_exchanges
    WHERE asked_at >= ?
    ORDER BY asked_at DESC
    LIMIT 20
"""


class AntiRepeatGate:
    def __init__(self, conn: sqlite3.Connection, jaccard_threshold: float = JACCARD_THRESHOLD):
        self.conn = conn
        self.threshold = jaccard_threshold

    def check(self, candidate: str) -> dict[str, Any]:
        """
        Returns {"duplicate": bool, "reason": str | None, "similarity": float | None}
        """
        candidate_tokens = _tokenize(candidate)
        cutoff = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()

        try:
            rows = self.conn.execute(_RECENT_Q_SQL, (cutoff,)).fetchall()
        except sqlite3.OperationalError:
            # checkin_exchanges table not yet created: no block
            return {"duplicate": False, "reason": None, "similarity": None}

        # Jaccard check against recent questions
        max_sim = 0.0
        for question_text, _ in rows:
            prior_tokens = _tokenize(question_text or "")
            sim = _jaccard(candidate_tokens, prior_tokens)
            if sim > max_sim:
                max_sim = sim
            if sim >= self.threshold:
                return {"duplicate": True, "reason": "jaccard_similarity", "similarity": round(sim, 3)}

        # Archetype cooldown check
        cutoff_24h = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        try:
            recent_24h = self.conn.execute(
                "SELECT question_text FROM checkin_exchanges WHERE asked_at >= ? LIMIT 50",
                (cutoff_24h,),
            ).fetchall()
        except sqlite3.OperationalError:
            recent_24h = []

        candidate_archetypes = _detect_archetypes(candidate)
        for archetype in candidate_archetypes:
            count = sum(
                1 for (q,) in recent_24h if archetype in _detect_archetypes(q or "")
            )
            if count >= ARCHETYPE_MAX_PER_DAY:
                return {
                    "duplicate": True,
                    "reason": f"archetype_cooldown:{archetype}",
                    "similarity": None,
                }

        return {"duplicate": False, "reason": None, "similarity": round(max_sim, 3)}
