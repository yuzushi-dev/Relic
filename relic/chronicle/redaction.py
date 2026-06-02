"""Redaction module for Chronicle, prevents secret/PII leakage in events.

Public API:
    contains_secret, redact_payload, redact_string
    SECRET_PATTERNS
"""
from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Patterns: compiled once at module load
# ---------------------------------------------------------------------------
_SECRET_PATTERN_DEFS: list[tuple[str, str]] = [
    # (name, pattern_string)
    ("api_key", r"api[_-]?key\s*[:=]\s*[\w-]{16,}"),
    ("bearer_token", r"bearer\s+[\w.-]{20,}"),
    ("pem_private_key", r"-----BEGIN\s+\w+\s+PRIVATE\s+KEY-----"),
    ("password", r"password\s*[:=]\s*\S{8,}"),
    ("openai_key", r"sk-[a-zA-Z0-9]{20,}"),
    ("github_token", r"ghp_[a-zA-Z0-9]{36}"),
    ("email", r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b"),
    ("slack_token", r"xox[baprs]-[a-zA-Z0-9-]{10,}"),
]

SECRET_PATTERNS: list[re.Pattern] = [
    re.compile(pattern, re.IGNORECASE) for _, pattern in _SECRET_PATTERN_DEFS
]

_PATTERN_NAMES: dict[re.Pattern, str] = {
    pattern: name for pattern, (name, _) in zip(SECRET_PATTERNS, _SECRET_PATTERN_DEFS)
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _to_text(payload: dict | str | bytes) -> str:
    """Coerce input to text for regex matching."""
    if isinstance(payload, bytes):
        return payload.decode("utf-8", errors="replace")
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        return str(payload)
    return str(payload)


def contains_secret(payload: dict | str | bytes) -> bool:
    """Return True if *payload* contains any secret pattern.

    Fail-open: logs error and returns False rather than raising.
    """
    try:
        text = _to_text(payload)
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                return True
        return False
    except Exception as exc:  # pragma: no cover
        logger.error("contains_secret check failed: %s", exc)
        return False


def redact_string(text: str) -> str:
    """Replace all secret matches in *text* with ``[REDACTED-{pattern_name}]``.

    Fail-open: on error, logs and returns the original text unchanged.
    """
    try:
        result = text
        for pattern in SECRET_PATTERNS:
            name = _PATTERN_NAMES[pattern]
            replacement = f"[REDACTED-{name}]"
            result = pattern.sub(replacement, result)
        return result
    except Exception as exc:  # pragma: no cover
        logger.error("redact_string failed: %s", exc)
        return text


def redact_payload(payload: dict) -> dict:
    """Return a *new* dict with all secret values redacted.

    Recursively walks nested dicts and string values. Non-string leaf values
    are preserved as-is.

    Fail-open: on error, logs and returns a shallow copy of the original.
    """
    try:
        return _redact_value(payload)
    except Exception as exc:  # pragma: no cover
        logger.error("redact_payload failed: %s", exc)
        return dict(payload)


def _redact_value(value: Any) -> Any:
    """Recursively redact a value (dict / list / str / other)."""
    if isinstance(value, dict):
        return {k: _redact_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, str):
        return redact_string(value)
    if isinstance(value, bytes):
        # Decode, redact, re-encode
        decoded = value.decode("utf-8", errors="replace")
        redacted = redact_string(decoded)
        return redacted.encode("utf-8")
    return value
