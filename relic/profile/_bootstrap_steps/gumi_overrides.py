"""TUI step: collect manual or hybrid Gumi domain overrides."""
from __future__ import annotations

import json
from typing import TextIO

from relic.profile._bootstrap_steps._io import prompt_optional, prompt_required

DOMAINS = [
    "identity",
    "embodiment",
    "place",
    "life_role",
    "routine",
    "passions",
    "social_world",
    "relationship_stance",
    "boundaries",
]

# Primary field per domain: used when researcher enters plain string instead of JSON.
_DOMAIN_PRIMARY_FIELD: dict[str, str | None] = {
    "identity": None,
    "embodiment": "gender_expression",
    "place": "location",
    "life_role": "occupation_or_study",
    "routine": "daily_schedule",
    "passions": None,           # comma list → primary_interests
    "social_world": None,       # too complex for plain text
    "relationship_stance": "attachment_style",
    "boundaries": "personal_space",
}

_DOMAIN_HINTS: dict[str, str] = {
    "identity": 'JSON: {"name": "...", "age": "..."}',
    "embodiment": '"feminine" oppure JSON: {"gender_expression": "feminine", "age_bracket": "mid adulthood"}',
    "place": '"coastal city" oppure JSON: {"location": "coastal city", "housing_situation": "rents apartment"}',
    "life_role": '"insegnante" oppure JSON: {"occupation_or_study": "educator", "life_stage": "established career"}',
    "routine": '"night owl" oppure JSON: {"daily_schedule": "night owl", "daily_pattern": "creative time-blocking"}',
    "passions": 'CSV es. "reading and writing, music" oppure JSON: {"primary_interests": [...], "hobbies": [...]}',
    "social_world": 'JSON: {"friends": ["few trusted friends"], "family_kinship": ["chosen family bonds"], "colleagues_contacts": [...]}',
    "relationship_stance": '"secure attachment" oppure JSON: {"attachment_style": "secure attachment", "intimacy_comfort": "open to intimacy"}',
    "boundaries": '"strong personal boundaries" oppure JSON: {"personal_space": "strong personal boundaries"}',
}


def _parse_override(domain: str, raw: str) -> dict:
    """Convert raw researcher input to a structured domain dict.

    Priority:
    1. If raw starts with '{' → try JSON parse.
    2. domain == 'passions' → split CSV into primary_interests.
    3. Domain has a primary field → wrap string in that key.
    4. Fallback → empty dict (domain stays skeleton from generator).
    """
    raw = raw.strip()
    if raw.startswith("{"):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass

    if domain == "passions":
        items = [s.strip() for s in raw.split(",") if s.strip()]
        return {"primary_interests": items, "hobbies": []}

    primary = _DOMAIN_PRIMARY_FIELD.get(domain)
    if primary:
        return {primary: raw}

    return {}


def collect_gumi_overrides(
    io_in: TextIO, io_out: TextIO, mode: str
) -> tuple[dict[str, dict], str, list[str]]:
    """Collect Gumi domain overrides, agent name, and signature emoji.

    Returns:
        (domain_overrides, agent_name, signature_emoji)
        domain_overrides maps domain → structured dict (ready for generator).
        signature_emoji is a list of 2-5 emoji chars identifying Gumi's voice.
    """
    if mode == "random":
        return {}, "Gumi", []
    print("\n--- Gumi Profile Overrides ---", file=io_out)
    print(
        "Inserire JSON strutturato o testo libero per ogni dominio.\n"
        "Modalità manual: tutti i campi richiesti. Hybrid: opzionali.",
        file=io_out,
    )
    agent_name = (
        prompt_optional("name", "Nome dell'agente Gumi.", io_in, io_out, default="Gumi") or "Gumi"
    )

    # Gumi signature emoji: her recurring expressive vocabulary
    raw_emoji = prompt_optional(
        "signature_emoji",
        "Emoji identificative di Gumi (2-5 emoji separate da spazio, es. '🌿 🌙 ✨'). Usate come vocabolario espressivo ricorrente.",
        io_in, io_out,
    )
    signature_emoji: list[str] = []
    if raw_emoji:
        signature_emoji = [e.strip() for e in raw_emoji.split() if e.strip()][:5]

    required = mode == "manual"
    result: dict[str, dict] = {}
    for domain in DOMAINS:
        hint = _DOMAIN_HINTS.get(domain, "")
        description = f"Override dominio '{domain}'. {hint}"
        if required:
            raw = prompt_required(domain, description, io_in, io_out)
            result[domain] = _parse_override(domain, raw)
        else:
            raw = prompt_optional(domain, description, io_in, io_out)
            if raw is not None:
                result[domain] = _parse_override(domain, raw)
    return result, agent_name, signature_emoji
