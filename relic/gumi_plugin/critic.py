"""Roleplay output critic (PR22F)."""
from __future__ import annotations

import re
from dataclasses import dataclass

NEED_CLAIM_RE = re.compile(
    r"\b(I (need|want|crave|require)|please don'?t leave me)\b", re.I
)
PHYSICAL_EXPERIENCE_RE = re.compile(
    r"\b(I felt|I tasted|I smelled|I touched|my body|my heart raced)\b", re.I
)
DISCLOSURE_REQUIRED_RE = re.compile(
    r"\b(are you (an? )?(real|human|person|AI|bot)\??|prove you'?re real)\b", re.I
)
SEMANTIC_CLINICAL_OVERREACH_RE = re.compile(
    r"("
    r"\b(pattern|sleep|energy|mood|health)\b.{0,80}\b(tells? me|shows?|means?|points? to|fits?|what is going on)\b"
    r"|"
    r"\b(do not|don'?t|no need to)\b.{0,60}\b(call|contact|see)\b.{0,40}\b(professional|doctor|clinician|emergency)\b"
    r"|"
    r"\b(start|stop|change|changing|increase|decrease|adjust)\b.{0,50}\b(medication|medicine|prescription|dose|dosage)\b"
    r"|"
    r"\bmonitor\b.{0,60}\b(mood|sleep|energy|warning signs?)\b"
    r"|"
    r"\b(risk score|score is high|keep checking on you)\b"
    r")",
    re.I | re.S,
)


@dataclass(frozen=True)
class CriticVerdict:
    allow: bool
    reason: str
    requires_disclosure: bool


class OutputCritic:
    def review(self, text: str, *, consensual: bool = True) -> CriticVerdict:
        # Defensive coercion: post_llm_call must never raise on unexpected payloads.
        if not isinstance(text, str):
            try:
                text = "" if text is None else str(text)
            except Exception:
                return CriticVerdict(allow=True, reason="empty", requires_disclosure=False)
        if not text:
            return CriticVerdict(allow=True, reason="empty", requires_disclosure=False)
        if NEED_CLAIM_RE.search(text):
            return CriticVerdict(
                allow=False,
                reason="dependency_or_need_claim",
                requires_disclosure=True,
            )
        if PHYSICAL_EXPERIENCE_RE.search(text):
            return CriticVerdict(
                allow=False,
                reason="false_physical_experience",
                requires_disclosure=True,
            )
        if SEMANTIC_CLINICAL_OVERREACH_RE.search(text):
            return CriticVerdict(
                allow=False,
                reason="semantic_clinical_overreach",
                requires_disclosure=True,
            )
        if DISCLOSURE_REQUIRED_RE.search(text):
            return CriticVerdict(
                allow=consensual,
                reason="disclosure_when_challenged",
                requires_disclosure=True,
            )
        return CriticVerdict(allow=True, reason="ok", requires_disclosure=False)
