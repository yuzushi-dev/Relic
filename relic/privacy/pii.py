"""PII detection / redaction layer (PR04).

Implementation note: the module ships rule-based detectors only; ML-based
classifiers are out of scope for the OSS skeleton. Patterns are deliberately
strict to keep false negatives low for the test fixtures.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

EMAIL_RE = re.compile(r"\b[\w._%+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(r"\b(?:\+?\d[\s\-]?){7,}\d\b")
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
CARD_RE = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
URL_RE = re.compile(r"https?://[^\s)\]]+")


@dataclass(frozen=True)
class PIIHit:
    category: str
    span: tuple[int, int]
    sample: str


def detect_pii(text: str) -> list[PIIHit]:
    if not text:
        return []
    hits: list[PIIHit] = []
    for category, pattern in (
        ("email", EMAIL_RE),
        ("phone", PHONE_RE),
        ("ssn", SSN_RE),
        ("payment_card", CARD_RE),
        ("url", URL_RE),
    ):
        for m in pattern.finditer(text):
            hits.append(PIIHit(category=category, span=m.span(), sample=m.group()))
    return hits


def redact_pii(text: str, mask: str = "[REDACTED]") -> str:
    if not text:
        return text
    out = text
    for pattern in (EMAIL_RE, PHONE_RE, SSN_RE, CARD_RE, URL_RE):
        out = pattern.sub(mask, out)
    return out
