"""Topic hint for Gumi proactive check-ins.

Wraps a sanitized question_hint string (from question_engine.build_question_hint)
into a formatted block for the check-in prompt, with anti-repeat guard.

Contract:
- Strips clinical scale references (ECR-R, DERS, SDT, ...)
- Forbidden-term filter uses FORBIDDEN_CLINICAL_TERMS from RuntimePackSanitizer
- Jaccard anti-repeat at threshold 0.60: if hint ≥ 0.60 similar to any recent → return ""
- Output: "--- spunto di conversazione ... ---\n{hint}" or ""
- ≤200 chars total, truncated at word boundary
"""
from __future__ import annotations

import re
from typing import Sequence

from relic.checkin.question_engine import SCALE_REF_RE
from relic.patterns.runtime_pack_sanitizer import FORBIDDEN_CLINICAL_TERMS

HEADER = "--- spunto di conversazione (solo per orientarti, non riprenderlo letteralmente) ---"

_JACCARD_THRESHOLD = 0.60


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"\b\w{3,}\b", text.lower()))


def _jaccard(a: set[str], b: set[str]) -> float:
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def _has_forbidden(text: str) -> bool:
    low = text.lower()
    return any(term in low for term in FORBIDDEN_CLINICAL_TERMS)


def render_topic_hint(question_hint: str, recent_messages: Sequence[str]) -> str:
    """Return topic hint block for the check-in prompt, or empty string.

    Args:
        question_hint: sanitized hint from question_engine.build_question_hint
        recent_messages: list of recent question texts (plain text, no timestamps)
    """
    hint = SCALE_REF_RE.sub("", question_hint.strip()).strip()
    if not hint:
        return ""

    if _has_forbidden(hint):
        import sys as _sys
        print(f"[topic_hint] blocked forbidden term in hint: {hint[:60]!r}", file=_sys.stderr)
        return ""

    # Anti-repeat: Jaccard similarity against recent question texts
    hint_tokens = _tokenize(hint)
    for msg in recent_messages:
        msg_tokens = _tokenize(msg)
        if _jaccard(hint_tokens, msg_tokens) >= _JACCARD_THRESHOLD:
            return ""

    result = f"{HEADER}\n{hint}"

    # Hard cap at 200 chars, truncated at word boundary
    if len(result) > 200:
        max_hint = 200 - len(HEADER) - 1  # 1 for newline
        truncated = hint[:max(0, max_hint)]
        last_space = truncated.rfind(" ")
        if last_space > 0:
            truncated = truncated[:last_space]
        result = f"{HEADER}\n{truncated}"

    return result
