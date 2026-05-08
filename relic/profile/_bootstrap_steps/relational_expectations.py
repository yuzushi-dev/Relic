"""TUI step: collect relational expectations baseline fields from subject/researcher."""
from __future__ import annotations

from typing import TextIO


_FIELDS = [
    (
        "desired_relationship_tone",
        "Quale tono relazionale desideri nella relazione con Gumi? (es. amichevole, professionale, neutro, informale)",
        str,
    ),
    (
        "continuity_expectations",
        "Quali sono le tue aspettative di continuità della relazione con Gumi nel tempo? (es. quotidiana, settimanale, as-needed)",
        str,
    ),
    (
        "disclosure_comfort_level",
        "Quale è il tuo livello di comfort nella condivisione di informazioni personali? (es. molto alto, moderato, basso, preferisco non rispondere)",
        str,
    ),
    (
        "role_expectations_for_gumi",
        "Quali sono le tue aspettative sul ruolo di Gumi? (es. supporto emotivo, compagnia, ascolto attivo, mentorship, altro)",
        str,
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


def collect_relational_expectations(io_in: TextIO, io_out: TextIO) -> dict:
    """Collect relational expectations baseline fields.

    Returns a dict where each value is {"value": str|None, "origin": "subject-stated"}.
    All fields are skippable; skipped fields have value=None.
    """
    print("\n=== Aspettative Relazionali ===", file=io_out)
    print(
        "Compilare i campi seguenti con le informazioni fornite dal soggetto.\n"
        "Ogni campo è opzionale: premere Invio per saltare.",
        file=io_out,
    )

    result: dict = {}
    for key, description, _ in _FIELDS:
        raw = _prompt_field(key, description, io_in, io_out)
        result[key] = {"value": raw, "origin": "subject-stated"}

    filled = sum(1 for v in result.values() if v["value"] is not None)
    print(f"\n  {filled}/{len(_FIELDS)} campi compilati.", file=io_out)
    return result
