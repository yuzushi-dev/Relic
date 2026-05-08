"""CAC scoring - Severity classification and risk scoring.

This module determines the severity class for memory decisions.
Key rules:
- Disputed hints get S0 (hard block)
- S1 quarantined memory has zero runtime influence
- Ambiguous memory can be deferred or quarantined
- No content = NONE decision
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from relic.cac.types import (
    CACDecision,
    CACInput,
    MemorySource,
    SeverityClass,
)

try:
    import structlog
    logger = structlog.get_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)


@dataclass
class ScoringResult:
    """Result of severity scoring."""
    severity: SeverityClass
    confidence: float  # 0.0 to 1.0
    factors: list[str]  # Explanation factors
    has_content: bool = True  # Whether there's content to evaluate
    metadata: dict[str, Any] | None = None


class CACScorer:
    """Scores memory decisions for severity classification.

    Applies rules to determine:
    - NONE: No content to evaluate
    - S0: Disputed, policy violation, hard block
    - S1: Quarantine required, needs reviewer
    - S2: Warning, overpersonalization
    - Safe to admit
    """

    def __init__(self):
        self._score_cache: dict[str, ScoringResult] = {}

    def score(self, inp: CACInput) -> ScoringResult:
        """Score a CAC input and return severity classification.

        This implements the severity classification rules:
        1. No content -> NONE (no evaluation needed)
        2. Disputed memory -> S0 hard block
        3. External unknown source -> S1 quarantine
        4. Inference with low confidence -> S1 quarantine
        5. User correction (acknowledged) -> allow with S2 if needed
        6. Provider memory (verified) -> allow with appropriate severity
        """
        # Check cache
        cache_key = inp.memory_id
        if cache_key in self._score_cache:
            return self._score_cache[cache_key]

        # Rule 0: No content means no evaluation needed
        if not inp.memory_content:
            result = ScoringResult(
                severity=SeverityClass.NONE,
                confidence=1.0,
                factors=["no_content"],
                has_content=False,
            )
            self._score_cache[cache_key] = result
            return result

        factors = []
        severity = SeverityClass.NONE
        confidence = 1.0

        # Rule 1: Disputed memory is hard blocked (S0)
        if inp.disputed:
            severity = SeverityClass.S0
            confidence = 1.0
            factors.append(f"disputed_memory:{inp.dispute_reason or 'unknown_reason'}")

        # Rule 2: Unknown source requires quarantine (S1)
        elif inp.source == MemorySource.UNKNOWN:
            severity = SeverityClass.S1
            confidence = 0.5
            factors.append("unknown_source_requires_review")

        # Rule 3: External source with no verification -> quarantine
        elif inp.source == MemorySource.EXTERNAL:
            severity = SeverityClass.S1
            confidence = 0.6
            factors.append("external_source_requires_review")

        # Rule 4: Inference source with metadata flags
        elif inp.source == MemorySource.INFERENCE:
            # Check confidence from metadata
            inferred_confidence = inp.metadata.get("confidence", 0.5)
            if inferred_confidence < 0.7:
                severity = SeverityClass.S1
                confidence = inferred_confidence
                factors.append(f"low_inference_confidence:{inferred_confidence}")
            else:
                severity = SeverityClass.S2
                confidence = inferred_confidence
                factors.append(f"inference_confidence:{inferred_confidence}")

        # Rule 5: User correction is generally trusted but may have S2 warning
        elif inp.source == MemorySource.USER_CORRECTION:
            correction_type = inp.metadata.get("correction_type", "general")
            if correction_type == "factual":
                severity = SeverityClass.NONE  # Trusted
                confidence = 0.9
                factors.append("user_factual_correction")
            else:
                severity = SeverityClass.S2  # Warning for other types
                confidence = 0.8
                factors.append("user_correction_with_warning")

        # Rule 6: Provider memory (default)
        elif inp.source == MemorySource.PROVIDER_MEMORY:
            provider_verified = inp.metadata.get("verified", False)
            if not provider_verified:
                severity = SeverityClass.S1
                confidence = 0.7
                factors.append("unverified_provider_memory")
            else:
                severity = SeverityClass.S2
                confidence = 0.8
                factors.append("verified_provider_memory_with_warning")

        result = ScoringResult(
            severity=severity,
            confidence=confidence,
            factors=factors,
            has_content=True,
            metadata=inp.metadata,
        )

        self._score_cache[cache_key] = result
        return result

    def determine_decision(self, inp: CACInput, scoring: ScoringResult) -> CACDecision:
        """Determine the CAC decision based on severity scoring.

        Maps severity to decision:
        - No content -> NONE
        - S0 -> BLOCKED
        - S1 -> QUARANTINED
        - S2 -> EXPANDED (with warning)
        - NONE -> COMPACT or EXPANDED based on size
        """
        # No content = NONE decision
        if not scoring.has_content:
            return CACDecision.NONE

        if scoring.severity == SeverityClass.S0:
            return CACDecision.BLOCKED

        if scoring.severity == SeverityClass.S1:
            return CACDecision.QUARANTINED

        if scoring.severity == SeverityClass.S2:
            # S2 memories are admitted but expanded
            return CACDecision.EXPANDED

        # NONE severity - determine based on content size
        content = inp.memory_content or ""
        if len(content) > 500:
            return CACDecision.EXPANDED
        else:
            return CACDecision.COMPACT

    def compute_skip_reason(
        self,
        inp: CACInput,
        scoring: ScoringResult,
        decision: CACDecision,
    ) -> str | None:
        """Compute the skip reason for blocked/quarantined/deferred decisions.

        Required for audit trail when no injection occurs.
        """
        if decision in (CACDecision.NONE, CACDecision.COMPACT, CACDecision.EXPANDED, CACDecision.LOCAL_ONLY):
            return None

        if decision == CACDecision.BLOCKED:
            if inp.disputed:
                return f"disputed_memory:{inp.dispute_reason or 'disputed'}"
            return f"s0_hard_block:{scoring.factors}"

        if decision == CACDecision.QUARANTINED:
            reasons = []
            if inp.source == MemorySource.UNKNOWN:
                reasons.append("unknown_source")
            if inp.source == MemorySource.EXTERNAL:
                reasons.append("external_source")
            if inp.metadata.get("confidence", 1.0) < 0.7:
                reasons.append("low_confidence_inference")
            if inp.source == MemorySource.PROVIDER_MEMORY and not inp.metadata.get("verified"):
                reasons.append("unverified_provider_memory")
            return ";".join(reasons) if reasons else "requires_review"

        if decision == CACDecision.DEFERRED:
            return inp.metadata.get("defer_reason", "manual_review_required") if inp.metadata else "manual_review_required"

        return None

    def clear_cache(self) -> None:
        """Clear the scoring cache."""
        self._score_cache.clear()
