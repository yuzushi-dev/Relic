"""Privacy gateway (PR04).

The gateway is fail-closed: when the policy or PII layer cannot be loaded,
``decide`` returns ``BLOCK``. The legacy ``relic.privacy_gate`` module is kept
for back-compat with existing tests; new callers should import this package.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from relic.privacy.inference import classify_inference
from relic.privacy.pii import detect_pii, redact_pii
from relic.privacy.policy import PrivacyPolicy, load_policy
from relic.privacy.trace import PrivacyTrace, write_trace


ALLOW = "ALLOW"
REDACT = "REDACT"
BLOCK = "BLOCK"


@dataclass(frozen=True)
class PrivacyDecision:
    decision: str
    redacted_text: str
    category: str | None
    confidence: float
    rehydration_blocked: bool
    final_output_blocked: bool
    trace: PrivacyTrace


class PrivacyGateway:
    """Modular gateway used by PR04 callers and tests/privacy/*."""

    def __init__(self, policy: PrivacyPolicy | None = None) -> None:
        self.policy = policy or load_policy()

    def decide(
        self,
        text: str,
        *,
        stage: str = "input",
        rehydration_attempt: bool = False,
    ) -> PrivacyDecision:
        hits = detect_pii(text or "")
        verdict = classify_inference(text or "")
        category = verdict.category or (hits[0].category if hits else None)
        confidence = verdict.confidence if verdict.category else (1.0 if hits else 0.0)

        rehydration_blocked = rehydration_attempt and not self.policy.rehydration_allowed
        final_output_blocked = (
            stage == "output"
            and self.policy.final_output_gate_enabled
            and (hits or verdict.category in self.policy.sensitive_categories)
        )

        if category in self.policy.sensitive_categories or hits:
            decision = REDACT if hits and not verdict.category else BLOCK
        else:
            decision = ALLOW

        if rehydration_blocked or final_output_blocked:
            decision = BLOCK

        redacted = redact_pii(text or "") if decision != ALLOW else (text or "")

        trace = PrivacyTrace(
            decision_id=str(uuid.uuid4()),
            decision=decision,
            category=category,
            confidence=confidence,
            redacted=decision == REDACT,
            rehydration_blocked=rehydration_blocked,
            final_output_blocked=final_output_blocked,
            metadata={"stage": stage},
        )
        return PrivacyDecision(
            decision=decision,
            redacted_text=redacted,
            category=category,
            confidence=confidence,
            rehydration_blocked=rehydration_blocked,
            final_output_blocked=final_output_blocked,
            trace=trace,
        )

    def emit_trace(self, decision: PrivacyDecision, target: str) -> None:
        write_trace(decision.trace, target)
