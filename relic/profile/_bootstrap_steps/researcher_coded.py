from __future__ import annotations

from typing import TextIO

_FIELDS: list[tuple[str, str]] = [
    (
        "attachment_style",
        "Stile di attaccamento osservato (es. secure, anxious, avoidant, disorganized).\n"
        "Lascia vuoto per saltare: ",
    ),
    (
        "communication_style",
        "Stile comunicativo prevalente (es. direct, indirect, verbose, terse).\n"
        "Lascia vuoto per saltare: ",
    ),
    (
        "affect_regulation_notes",
        "Note sulla regolazione affettiva osservata (strategie, pattern, trigger).\n"
        "Lascia vuoto per saltare: ",
    ),
    (
        "cultural_context_notes",
        "Note sul contesto culturale rilevante per l'interazione.\n"
        "Lascia vuoto per saltare: ",
    ),
]


def collect_researcher_coded_fields(io_in: TextIO, io_out: TextIO) -> dict:
    """Collect researcher-coded fields. Returns dict of {field: {value, origin}}."""
    io_out.write("\n=== Campi codificati dal ricercatore ===\n")
    io_out.write("(Valutazione del ricercatore — non auto-dichiarata dal soggetto)\n\n")

    result: dict = {}
    for field, prompt in _FIELDS:
        io_out.write(prompt)
        io_out.flush()
        raw = io_in.readline().strip()
        result[field] = {
            "value": raw if raw else None,
            "origin": "researcher-coded",
        }

    return result
