"""TUI step: collect interaction preferences from subject."""
from __future__ import annotations

from typing import TextIO


_FIELDS = [
    (
        "message_length_preference",
        "Preferenza lunghezza messaggi (es. breve, medio, lungo, adattabile).",
        str,
    ),
    (
        "emoji_visual_preference",
        "Preferenza per uso emoji (es. niente, pochi, molti, non importa).",
        str,
    ),
    (
        "response_timing_expectation",
        "Aspettativa di tempistica risposte (es. immediato, entro ore, non urgente).",
        str,
    ),
    (
        "preferred_topics",
        "Argomenti preferiti (separati da virgola, es. tecnologia, filosofia, sport). Skippabile.",
        list,
    ),
    (
        "avoided_topics",
        "Argomenti da evitare (separati da virgola, es. politica, religione). Skippabile.",
        list,
    ),
]


def _prompt_field(label: str, description: str, io_in: TextIO, io_out: TextIO) -> str | None:
    print(f"\n  {description}", file=io_out)
    print(f"  {label} (invio per saltare): ", end="", flush=True, file=io_out)
    try:
        line = io_in.readline()
    except (EOFError, OSError):
        line = ""
    value = line.strip() if line else ""
    return value if value else None


def _prompt_array_field(label: str, description: str, io_in: TextIO, io_out: TextIO) -> list[str]:
    print(f"\n  {description}", file=io_out)
    print(f"  {label} (invio per saltare): ", end="", flush=True, file=io_out)
    try:
        line = io_in.readline()
    except (EOFError, OSError):
        line = ""
    value = line.strip() if line else ""
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def collect_interaction_preferences(io_in: TextIO, io_out: TextIO) -> dict:
    """Collect interaction preferences from subject.

    Returns a dict where:
    - labeled_string fields have {"value": str|None, "origin": "subject-stated"}
    - labeled_string_array fields have {"values": list[str], "origin": "subject-stated"}
    All fields are skippable.
    """
    print("\n=== Preferenze di Interazione ===", file=io_out)
    print(
        "Compilare i campi seguenti con le informazioni fornite dal soggetto.\n"
        "Ogni campo è opzionale: premere Invio per saltare.",
        file=io_out,
    )

    result: dict = {}
    for key, description, field_type in _FIELDS:
        if field_type == list:
            raw = _prompt_array_field(key, description, io_in, io_out)
            result[key] = {"values": raw, "origin": "subject-stated"}
        else:
            raw = _prompt_field(key, description, io_in, io_out)
            result[key] = {"value": raw, "origin": "subject-stated"}

    filled = sum(
        1
        for v in result.values()
        if (isinstance(v, dict) and v.get("value") is not None)
        or (isinstance(v, dict) and v.get("values"))
    )
    print(f"\n  {filled}/{len(_FIELDS)} campi compilati.", file=io_out)
    return result
