"""
Confidence Caps for Sensitive Signals.

Implements baseline comparison and confidence caps per PR32D rules.
"""

from dataclasses import dataclass
from typing import Optional, Dict


# Confidence Caps
BASELINE_UNKNOWN_CAP = 0.35
SINGLE_EVENT_NON_CRISIS_CAP = 0.30
TWO_EVENTS_CAP = 0.55
THREE_OR_MORE_CAP = 0.75
HUMAN_REVIEWED_CAP = 0.85
MAXIMUM_CAP = 0.85


@dataclass
class ConfidenceCaps:
    """Confidence cap rules for sensitive signals."""
    baseline_unknown: float = BASELINE_UNKNOWN_CAP
    single_event_non_crisis: float = SINGLE_EVENT_NON_CRISIS_CAP
    two_events: float = TWO_EVENTS_CAP
    three_or_more: float = THREE_OR_MORE_CAP
    human_reviewed: float = HUMAN_REVIEWED_CAP
    maximum: float = MAXIMUM_CAP


@dataclass
class BaselineComparison:
    """Baseline comparison data."""
    baseline_confidence: float
    current_confidence: float
    delta: float


class ConfidenceCapEngine:
    """
    Applies confidence caps to sensitive signals.

    Rules:
    - baseline_unknown: capped at 0.35
    - single_event_non_crisis: capped at 0.30
    - two_events: capped at 0.55
    - three_or_more: capped at 0.75
    - human_reviewed: capped at 0.85
    - No signal ever exceeds 0.85
    """

    def __init__(self):
        self.caps = ConfidenceCaps()

    def apply_cap(
        self,
        event_count: int,
        baseline_confidence: Optional[float] = None,
        human_reviewed: bool = False
    ) -> float:
        """
        Apply confidence caps to a signal.

        Args:
            event_count: Number of events contributing to signal
            baseline_confidence: Optional baseline confidence
            human_reviewed: Whether signal has been human reviewed

        Returns:
            Capped confidence value (never exceeds 0.85)
        """
        # If baseline unknown, apply baseline cap
        if baseline_confidence is not None:
            # Baseline comparison determines starting confidence
            confidence = min(baseline_confidence, BASELINE_UNKNOWN_CAP)
            return min(confidence, MAXIMUM_CAP)

        # Human reviewed gets higher cap
        if human_reviewed:
            return HUMAN_REVIEWED_CAP

        # Apply event-count caps
        if event_count == 0:
            return BASELINE_UNKNOWN_CAP
        elif event_count == 1:
            return SINGLE_EVENT_NON_CRISIS_CAP
        elif event_count == 2:
            return TWO_EVENTS_CAP
        else:
            return THREE_OR_MORE_CAP

    def compare_to_baseline(
        self,
        current_confidence: float,
        baseline_confidence: float
    ) -> BaselineComparison:
        """
        Compare current confidence to baseline.

        Args:
            current_confidence: Current signal confidence
            baseline_confidence: Baseline confidence

        Returns:
            BaselineComparison with delta
        """
        return BaselineComparison(
            baseline_confidence=baseline_confidence,
            current_confidence=current_confidence,
            delta=current_confidence - baseline_confidence
        )

    def get_cap_for_event_count(self, event_count: int) -> float:
        """Get cap for specific event count."""
        if event_count == 0:
            return BASELINE_UNKNOWN_CAP
        elif event_count == 1:
            return SINGLE_EVENT_NON_CRISIS_CAP
        elif event_count == 2:
            return TWO_EVENTS_CAP
        else:
            return THREE_OR_MORE_CAP

    def validate_no_signal_above_085(self, confidence: float) -> bool:
        """
        Validate confidence does not exceed 0.85.

        BLOCKED_SIGNAL_ABOVE_085
        """
        return confidence <= MAXIMUM_CAP
