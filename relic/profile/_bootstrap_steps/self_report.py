"""TUI step: collect self-report baseline fields from subject/researcher."""
from __future__ import annotations

from typing import TextIO


_FIELDS = [
    (
        "preferred_name",
        "Come preferisce essere chiamato/a il soggetto? (nome, soprannome, ecc.)",
        str,
    ),
    (
        "age_range",
        "Fascia d'età del soggetto (es. 18-25, 26-35, 36-45, 46-55, 56+).",
        str,
    ),
    (
        "gender_identity",
        "Identità di genere dichiarata dal soggetto (es. uomo, donna, non-binary, preferisce non rispondere).",
        str,
    ),
    (
        "preferred_pronoun",
        "Pronome con cui riferirsi al soggetto in italiano (lui / lei / forme neutre). "
        "Determina l'accordo grammaticale; utile soprattutto se non-binary. Skippabile.",
        str,
    ),
    (
        "language",
        "Lingua principale del soggetto (es. it, en, fr). Codice ISO 639-1 o nome esteso.",
        str,
    ),
    (
        "contact_channel_preference",
        "Canale di contatto preferito dal soggetto (es. telegram, email, sms).",
        str,
    ),
    (
        "occupation_or_study",
        "Occupazione o campo di studio del soggetto (es. insegnante, studente ingegneria, infermiere).",
        str,
    ),
    (
        "location",
        "Tipo di contesto geografico del soggetto (es. coastal city, urban center, rural village, mountain town).",
        str,
    ),
    (
        "family_structure",
        "Struttura familiare del soggetto (es. single, coppia senza figli, genitore, famiglia allargata).",
        str,
    ),
    (
        "narrative_self_description",
        "Breve descrizione narrativa del soggetto in prima persona (max 2-3 frasi). Skippabile.",
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


def collect_self_report_fields(io_in: TextIO, io_out: TextIO) -> dict:
    """Collect self-report baseline fields.

    Returns a dict where each value is {"value": str|None, "origin": "subject-stated"}.
    All fields are skippable; skipped fields have value=None.
    """
    print("\n--- Dati Self-Report del Soggetto ---", file=io_out)
    print(
        "Compilare i campi seguenti con le informazioni fornite dal soggetto.\n"
        "Ogni campo è opzionale: premere Invio per saltare.",
        file=io_out,
    )

    _DEFAULTS = {
        "contact_channel_preference": "telegram",
    }

    result: dict = {}
    for key, description, _ in _FIELDS:
        raw = _prompt_field(key, description, io_in, io_out)
        if raw is None and key in _DEFAULTS:
            raw = _DEFAULTS[key]
        result[key] = {"value": raw, "origin": "subject-stated"}

    filled = sum(1 for v in result.values() if v["value"] is not None)
    print(f"\n  {filled}/{len(_FIELDS)} campi compilati.", file=io_out)
    return result
