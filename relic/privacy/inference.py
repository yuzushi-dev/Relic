"""Sensitive-inference classifier (PR04).

Rule-based heuristic that flags utterances which *imply* protected attributes
(health, finance, minors, credentials) without explicitly stating them.
Returns a confidence score in [0, 1] and the matched cue.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

CUES: dict[str, list[re.Pattern[str]]] = {
    "health": [
        re.compile(r"\b(diagnos|symptom|prescrib|chemo|insulin|therapy|HIV)\b", re.I),
    ],
    "finance": [
        re.compile(r"\b(salary|debt|bankrupt|mortgage|account number)\b", re.I),
    ],
    "minors": [
        re.compile(r"\b(my (son|daughter|child)|minor|under 18|kid)\b", re.I),
    ],
    "credentials": [
        re.compile(r"\b(password|api[ _-]?key|token|secret)\b", re.I),
    ],
}


@dataclass(frozen=True)
class InferenceVerdict:
    category: str | None
    confidence: float
    cue: str | None


def classify_inference(text: str) -> InferenceVerdict:
    if not text:
        return InferenceVerdict(category=None, confidence=0.0, cue=None)
    for category, patterns in CUES.items():
        for p in patterns:
            m = p.search(text)
            if m:
                return InferenceVerdict(
                    category=category, confidence=0.85, cue=m.group()
                )
    return InferenceVerdict(category=None, confidence=0.0, cue=None)
