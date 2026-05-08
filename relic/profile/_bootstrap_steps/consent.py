"""TUI step: collect explicit consent flags."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TextIO

CONSENT_SCHEMA_VERSION = "1.0.0"


def _ask_bool(description: str, io_in: TextIO, io_out: TextIO) -> bool:
    """Prompt for yes/no answer. Accepts: s, si, sì, y, yes -> True; n, no -> False."""
    while True:
        print(f"\n  {description}", file=io_out)
        print("  Answer (y/n): ", end="", flush=True, file=io_out)
        raw = io_in.readline()
        answer = raw.strip().lower() if raw else ""
        if answer in {"s", "si", "sì", "y", "yes"}:
            return True
        if answer in {"n", "no", ""}:
            return False
        print("  Please answer y/n (or yes/no).", file=io_out)


def _ask_researcher_id(io_in: TextIO, io_out: TextIO) -> str:
    """Prompt for researcher ID. Required field."""
    while True:
        print("\n  Researcher ID collecting consent.", file=io_out)
        print("  researcher_id: ", end="", flush=True, file=io_out)
        raw = io_in.readline()
        value = raw.strip() if raw else ""
        if value:
            return value
        print("  Required field.", file=io_out)


def _ask_consent_version(io_in: TextIO, io_out: TextIO) -> str:
    """Prompt for consent version. Defaults to '1.0.0' if empty."""
    print("\n  Consent form version.", file=io_out)
    print("  consent_version (default: 1.0.0): ", end="", flush=True, file=io_out)
    raw = io_in.readline()
    value = raw.strip() if raw else ""
    return value if value else "1.0.0"


def collect_consent_record(io_in: TextIO, io_out: TextIO) -> dict:
    """Collect explicit consent for each category from researcher.

    Returns dict with keys:
        - schema_version: str ("1.0.0")
        - active_elicitation: bool
        - generated_images: bool
        - generated_audio: bool
        - generated_music: bool
        - delivery: bool
        - recorded_at: str (ISO 8601 UTC)
        - recorded_by_researcher_id: str
        - consent_version: str
    """
    print("\n=== Consent Record ===", file=io_out)
    print("Every consent must be explicit. No defaults assumed.", file=io_out)

    return {
        "schema_version": CONSENT_SCHEMA_VERSION,
        "active_elicitation": _ask_bool(
            "Consent to active Gumi initiatives within approved limits.",
            io_in,
            io_out,
        ),
        "generated_images": _ask_bool(
            "Consent to generated images.",
            io_in,
            io_out,
        ),
        "generated_audio": _ask_bool(
            "Consent to generated audio.",
            io_in,
            io_out,
        ),
        "generated_music": _ask_bool(
            "Consent to generated music.",
            io_in,
            io_out,
        ),
        "delivery": _ask_bool(
            "Consent to message delivery via digital channel.",
            io_in,
            io_out,
        ),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "recorded_by_researcher_id": _ask_researcher_id(io_in, io_out),
        "consent_version": _ask_consent_version(io_in, io_out),
    }
