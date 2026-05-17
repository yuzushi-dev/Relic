"""Topic hint for Gumi proactive check-ins.

Wraps a sanitized question_hint string (from question_engine.build_question_hint)
into a formatted block for the check-in prompt, with anti-repeat guard.

Contract:
- Strips clinical scale references (ECR-R, DERS, SDT, ...)
- Jaccard anti-repeat: if hint ≥ 0.85 similar to any recent message → return ""
- Output: "--- spunto di conversazione ... ---\n{hint}" or ""
- ≤200 chars total
"""
from __future__ import annotations

import re
from typing import Sequence

# Same pattern as question_engine._SCALE_REF_RE
_SCALE_REF_RE = re.compile(r"\s*\([A-Z][A-Za-z0-9][A-Za-z0-9\-]*\)")

# Forbidden clinical terms that must never appear in output
_FORBIDDEN_TERMS = {
    "disorder", "syndrome", "diagnosis", "diagnosi", "clinical",
    "clinico", "psychological", "psicologico",
}

HEADER = "--- spunto di conversazione (solo per orientarti, non riprenderlo letteralmente) ---"

_JACCARD_THRESHOLD = 0.85


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"\b\w{3,}\b", text.lower()))


def _jaccard(a: set[str], b: set[str]) -> float:
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def _strip_scales(text: str) -> str:
    return _SCALE_REF_RE.sub("", text).strip()


def _has_forbidden(text: str) -> bool:
    low = text.lower()
    return any(term in low for term in _FORBIDDEN_TERMS)


def render_topic_hint(question_hint: str, recent_messages: Sequence[str]) -> str:
    """Return topic hint block for the check-in prompt, or empty string.

    Args:
        question_hint: sanitized hint from question_engine.build_question_hint
        recent_messages: list of recent message texts (plain text, no timestamps)
    """
    hint = _strip_scales(question_hint.strip())
    if not hint:
        return ""

    # Drop if forbidden term leaked through (defensive)
    if _has_forbidden(hint):
        return ""

    # Anti-repeat: Jaccard similarity against recent messages
    hint_tokens = _tokenize(hint)
    for msg in recent_messages:
        msg_tokens = _tokenize(msg)
        if _jaccard(hint_tokens, msg_tokens) >= _JACCARD_THRESHOLD:
            return ""

    result = f"{HEADER}\n{hint}"

    # Hard cap at 200 chars
    if len(result) > 200:
        # Truncate hint, preserve header
        max_hint = 200 - len(HEADER) - 1  # 1 for newline
        result = f"{HEADER}\n{hint[:max(0, max_hint)]}"

    return result
