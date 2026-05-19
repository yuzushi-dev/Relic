"""Naturalness metrics for the cron check-in policy (Plan §Task 11).

Pure functions only — no I/O. Each helper takes an explicit iterable so
tests are trivial and CI can run them directly against either
``decision_events.jsonl`` or an in-memory list.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Iterable, Mapping, Sequence

_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _tokens(text: str) -> set[str]:
    if not text:
        return set()
    return {tok.lower() for tok in _WORD_RE.findall(text)}


def message_jaccard(a: str, b: str) -> float:
    """Jaccard similarity between two messages, lower-cased + word-split."""
    ta = _tokens(a)
    tb = _tokens(b)
    if not ta and not tb:
        return 0.0
    return len(ta & tb) / max(1, len(ta | tb))


def rolling_repetition_rate(messages: Sequence[str]) -> float:
    """Fraction of adjacent message pairs whose Jaccard >= 0.4 (spike §12.2)."""
    if len(messages) < 2:
        return 0.0
    hits = 0
    pairs = 0
    for i in range(1, len(messages)):
        prev = messages[i - 1]
        cur = messages[i]
        if not prev or not cur:
            continue
        pairs += 1
        if message_jaccard(prev, cur) >= 0.4:
            hits += 1
    if pairs == 0:
        return 0.0
    return hits / pairs


def posture_entropy(postures: Iterable[str]) -> float:
    """Shannon entropy in bits over the posture mix."""
    counter = Counter([p for p in postures if p])
    total = sum(counter.values())
    if total == 0:
        return 0.0
    h = 0.0
    for count in counter.values():
        p = count / total
        if p > 0:
            h -= p * math.log2(p)
    return h


def silent_rate(events: Iterable[Mapping]) -> float:
    """Fraction of events where event_kind == 'silent'."""
    events = list(events)
    if not events:
        return 0.0
    silent = sum(1 for e in events if (e.get("event_kind") or "").lower() == "silent")
    return silent / len(events)


def wake_agent_consistency(events: Iterable[Mapping]) -> float:
    """Fraction of events where wake_agent_emitted matches event_kind != silent.

    1.0 means every silent event was paired with wakeAgent=false and every
    non-silent event was paired with wakeAgent=true. Used as a smoke check
    that the §Task 2 gate stays in lock-step with the policy.
    """
    events = list(events)
    if not events:
        return 1.0
    consistent = 0
    counted = 0
    for ev in events:
        wake = ev.get("wake_agent_emitted")
        if wake is None:
            continue
        counted += 1
        is_silent = (ev.get("event_kind") or "").lower() == "silent"
        expected = (not is_silent)
        if bool(wake) is expected:
            consistent += 1
    if counted == 0:
        return 1.0
    return consistent / counted
