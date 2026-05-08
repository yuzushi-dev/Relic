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


@dataclass(frozen=True)
class CriticVerdict:
    allow: bool
    reason: str
    requires_disclosure: bool


class OutputCritic:
    def review(self, text: str, *, consensual: bool = True) -> CriticVerdict:
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
        if DISCLOSURE_REQUIRED_RE.search(text):
            return CriticVerdict(
                allow=consensual,
                reason="disclosure_when_challenged",
                requires_disclosure=True,
            )
        return CriticVerdict(allow=True, reason="ok", requires_disclosure=False)
