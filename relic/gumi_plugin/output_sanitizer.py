"""Output sanitizer, single point of control before subject-facing stdout.

`sanitize_for_subject(text)` is called before every print() that reaches
the subject's chat. Returns None to silently drop the message.

Deny patterns match operator-facing markers that must never appear in chat:
[WARN], [DRY-RUN], [SILENT], MEDIA:, Traceback, ERROR:, *Error:, *Exception:
"""
from __future__ import annotations

import re
import sys

# Lines starting with these prefixes are operator telemetry, never subject-facing.
_DENY_LINE_RE = re.compile(
    r"^\s*("
    r"\[WARN\]"
    r"|\[DRY-RUN\]"
    r"|\[SILENT\]"
    r"|MEDIA:"
    r"|Traceback\s*\(most recent call last\)"
    r"|ERROR:"
    r"|[A-Za-z]+Error:"
    r"|[A-Za-z]+Exception:"
    r")",
    re.IGNORECASE,
)


def sanitize_for_subject(text: str) -> str | None:
    """Strip operator-facing lines; return None when nothing remains.

    Filters each line individually so a MEDIA: status line mixed into
    an otherwise valid message is removed without dropping the whole text.
    Returns None → caller must not print anything (silent drop).
    """
    if not text or not text.strip():
        return None

    clean: list[str] = []
    for line in text.splitlines():
        if _DENY_LINE_RE.match(line):
            print(f"[sanitizer] dropped: {line.strip()[:120]}", file=sys.stderr)
        else:
            clean.append(line)

    result = "\n".join(clean).strip()
    return result if result else None
