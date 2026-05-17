"""Style hints for Gumi proactive check-ins.

Translates whitelisted interaction facets into plain-language Italian directives.
Never exposes raw facet keys, numeric values, or clinical terminology.

Contract:
- Only 5 whitelisted interaction facets are eligible
- Confidence floor: 0.20 (low_initial = 0.10 → no bullet)
- correction_state in {corrected, disputed, blocked} → skip facet
- directness_preference: bullet at both extremes (≥0.65 or ≤0.35), neutral → silent
- Other 4 facets: bullet only at low end (≤0.35), high tolerance → no constraint
- Output: "--- come scriverle questo messaggio ---\n- bullet\n..." or ""
- Max 5 bullets, ≤400 chars total
"""
from __future__ import annotations

_CONFIDENCE_MAP = {
    "high":        0.80,
    "medium":      0.50,
    "low":         0.25,
    "low_initial": 0.10,
}

_CONFIDENCE_FLOOR = 0.20

_BLOCKED_CORRECTION_STATES = {"corrected", "disputed", "blocked"}

HEADER = "--- come scriverle questo messaggio ---"


def _confidence_float(facet: dict) -> float:
    if "confidence_float" in facet:
        return float(facet["confidence_float"])
    return _CONFIDENCE_MAP.get(str(facet.get("confidence", "low_initial")), 0.10)


def _correction_state(facet: dict) -> str:
    return str(facet.get("correction_state", "active"))


def render_style_hints(interaction: dict[str, dict]) -> str:
    """Return style hint block for the check-in prompt, or empty string.

    Args:
        interaction: the `interaction` section of subject_baseline.json
    """
    bullets: list[str] = []

    # --- directness_preference: bullet at both extremes ---
    dp = interaction.get("directness_preference")
    if dp and isinstance(dp, dict):
        if _correction_state(dp) not in _BLOCKED_CORRECTION_STATES:
            if _confidence_float(dp) >= _CONFIDENCE_FLOOR:
                val = float(dp.get("value", 0.5))
                if val >= 0.65:
                    bullets.append("lui preferisce messaggi diretti, senza preamboli")
                elif val <= 0.35:
                    bullets.append("lui preferisce un tono più morbido, indiretto")

    # --- negative-band-only facets: bullet only when value ≤ 0.35 ---
    _negative_band: list[tuple[str, str]] = [
        ("humor_tolerance",             "evita battute o ironia in questo messaggio"),
        ("emotional_intensity_tolerance", "mantieni un registro contenuto, evita slanci emotivi"),
        ("proactive_contact_tolerance",  "stai leggera, troppa iniziativa pesa"),
        ("fictional_diegesis_tolerance", "stai sul concreto, evita riferimenti a scene immaginarie"),
    ]

    for key, directive in _negative_band:
        if len(bullets) >= 5:
            break
        facet = interaction.get(key)
        if not facet or not isinstance(facet, dict):
            continue
        if _correction_state(facet) in _BLOCKED_CORRECTION_STATES:
            continue
        if _confidence_float(facet) < _CONFIDENCE_FLOOR:
            continue
        if float(facet.get("value", 1.0)) <= 0.35:
            bullets.append(directive)

    if not bullets:
        return ""

    lines = [HEADER] + [f"- {b}" for b in bullets]
    result = "\n".join(lines)

    # Safety: hard cap at 400 chars
    if len(result) > 400:
        result = result[:400]

    return result
