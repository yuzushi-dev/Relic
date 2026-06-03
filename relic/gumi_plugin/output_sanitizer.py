"""Output sanitizer, single point of control before subject-facing stdout.

`sanitize_for_subject(text)` is called before every print() that reaches
the subject's chat. Returns None to silently drop the message.

Deny patterns match operator-facing markers that must never appear in chat:
[WARN], [DRY-RUN], [SILENT], MEDIA:, Traceback, ERROR:, *Error:, *Exception:
"""
from __future__ import annotations

import re
import sys

_TRAILING_SYMBOL_RE = re.compile(
    r"(\s*(?:[\U0001F300-\U0001FAFF\u2600-\u27BF]\ufe0f?|\ufe0f)+\s*)$"
)
_TERMINAL_FULL_STOP_RE = re.compile(
    r"\.+(?=(?:\s*(?:[\U0001F300-\U0001FAFF\u2600-\u27BF]\ufe0f?|\ufe0f))*\s*$)"
)

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


def strip_terminal_full_stops(text: str) -> str:
    """Remove only terminal full stops, preserving other punctuation."""
    cleaned: list[str] = []
    for line in text.splitlines():
        suffix_match = _TRAILING_SYMBOL_RE.search(line.rstrip())
        suffix = suffix_match.group(1) if suffix_match else ""
        without_stop = _TERMINAL_FULL_STOP_RE.sub("", line)
        if suffix and without_stop.endswith(suffix):
            # Collapse whitespace left behind by "text. ✨" -> "text ✨".
            body = without_stop[: -len(suffix)].rstrip()
            without_stop = f"{body} {suffix.lstrip()}"
        cleaned.append(without_stop)
    return "\n".join(cleaned)


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

    result = strip_terminal_full_stops("\n".join(clean)).strip()
    return result if result else None
