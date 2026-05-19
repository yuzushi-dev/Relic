"""Runtime aggregation for non-crisis safety signals.

Hermes hooks see one user turn at a time. This module aggregates redacted
signal references across turns so non-crisis notifications are based on a
pattern, not a single mention.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import time
from typing import Dict, Tuple

from relic.patterns.signal_extractor import (
    THREE_OR_MORE_CAP,
    TWO_EVENTS_CAP,
    SensitiveSignal,
    SignalDisposition,
    WarningTier,
)


@dataclass
class AggregatedSignal:
    """Aggregated signal state with no raw user text."""

    subject_id: str
    signal_family: str
    evidence_refs: list[str]
    event_count: int
    confidence: float
    warning_tier: str
    should_notify: bool
    already_notified: bool = False


class InMemorySafetySignalAggregator:
    """Small best-effort aggregator for Hermes runtime hooks.

    It intentionally stores only signal family names and evidence refs. Raw user
    text remains in the extractor call and is not retained here.
    """

    def __init__(self, *, window_seconds: int = 60 * 60 * 24, notify_after_events: int = 2) -> None:
        self.window_seconds = window_seconds
        self.notify_after_events = notify_after_events
        self._signals: Dict[Tuple[str, str], AggregatedSignal] = {}
        self._timestamps: Dict[Tuple[str, str], float] = {}

    def record(self, signal: SensitiveSignal) -> AggregatedSignal:
        key = (signal.subject_id, signal.signal_family)
        now = time()
        previous = self._signals.get(key)
        previous_ts = self._timestamps.get(key, now)

        if previous is None or now - previous_ts > self.window_seconds:
            refs = list(dict.fromkeys(signal.evidence_refs))
            event_count = signal.event_count
            already_notified = False
        else:
            refs = list(dict.fromkeys(previous.evidence_refs + signal.evidence_refs))
            event_count = len(refs)
            already_notified = previous.already_notified

        if event_count >= 3:
            confidence = THREE_OR_MORE_CAP
            tier = WarningTier.T3_INTERRUPTIVE.value
        elif event_count == 2:
            confidence = TWO_EVENTS_CAP
            tier = WarningTier.T2_REVIEW.value
        else:
            confidence = signal.confidence
            tier = signal.warning_tier

        should_notify = event_count >= self.notify_after_events and not already_notified
        aggregated = AggregatedSignal(
            subject_id=signal.subject_id,
            signal_family=signal.signal_family,
            evidence_refs=refs,
            event_count=event_count,
            confidence=confidence,
            warning_tier=tier,
            should_notify=should_notify,
            already_notified=already_notified or should_notify,
        )
        self._signals[key] = aggregated
        self._timestamps[key] = now
        signal.disposition = SignalDisposition.NOTIFIED.value if should_notify else SignalDisposition.QUEUED.value
        return aggregated

    def clear(self) -> None:
        self._signals.clear()
        self._timestamps.clear()
