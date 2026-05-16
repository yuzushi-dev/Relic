"""Context injection sources and per-turn ephemeral injection for Hermes plugin.

inject_context() is the pre_llm_call callback registered with Hermes.
It builds the PromptContextPack and returns {"context": redacted_text}.

Constraints:
- NEVER include the raw user message in the returned context.
- NEVER write to SOUL.md, MEMORY.md, USER.md.
- Fail-open: any exception returns None so Hermes skips the hook silently.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

# Markers whose presence in the outgoing context string indicates a raw-prompt leak.
_RAW_PROMPT_LEAK_MARKERS = (
    "SECRET_RAW_PROMPT_SHOULD_NOT_APPEAR",
    "raw_final_prompt",
)


class ContextSource(str, Enum):
    """Independent context sources — never monolithic."""
    MEMORY = "memory"
    USER = "user"
    SYSTEM = "system"
    SKILL = "skill"
    SOUL = "soul"
    DIARY = "diary"
    WORLD_STATE = "world_state"
    MULTI_PROVIDER_AGGREGATION = "multi_provider_aggregation"
    PROJECT_WORKFLOW = "project_workflow"
    USER_PRIVATE_FACTS = "user_private_facts"

    @classmethod
    def list_all(cls) -> list["ContextSource"]:
        return list(cls)


def _check_no_raw_leak(text: str) -> None:
    """Raise ValueError if any raw-prompt marker is present in text."""
    for marker in _RAW_PROMPT_LEAK_MARKERS:
        if marker in text:
            raise ValueError(f"Raw-prompt leak detected: marker '{marker}' in injected context")


def _load_subject_profile_fields(subject_id: str) -> dict[str, Any]:
    """Load relevant personalisation fields from baseline_user_profile.json.

    Returns an empty dict on any error so callers fail-open.
    """
    import json
    from pathlib import Path

    try:
        from relic.profile.registry import ProfileRegistry

        registry = ProfileRegistry()
        profile = registry.get_subject(subject_id)
        if profile is None:
            return {}
        baseline_path = profile.relic_subject_home / "baseline_user_profile.json"
        if not baseline_path.exists():
            return {}
        with open(baseline_path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as exc:
        logger.warning("_load_subject_profile_fields failed for %s: %s", subject_id, exc)
        return {}


def _build_user_private_facts(fields: dict[str, Any]) -> str:
    """Build a redacted system-guidance block from collected profile fields.

    Never includes researcher-coded notes or clinical terms.
    """
    lines: list[str] = []

    def _srval(key: str) -> str | None:
        sr = fields.get("self_report_fields", {})
        raw = (
            fields.get(key)
            or sr.get(key)
            or fields.get("self_report", {}).get(key)
        )
        if isinstance(raw, dict):
            return raw.get("value") or None
        return raw or None

    preferred_name = _srval("preferred_name")
    if preferred_name:
        lines.append(f"Nome preferito: {preferred_name}")

    language = _srval("language")
    if language:
        lines.append(f"Lingua preferita: {language}")

    ip = fields.get("interaction_preferences", {})

    def _ipval(key: str) -> Any:
        v = ip.get(key) or fields.get(key)
        if isinstance(v, dict):
            return v.get("value") or v.get("values")
        return v

    preferred_topics = _ipval("preferred_topics")
    avoided_topics = _ipval("avoided_topics")
    msg_length = _ipval("message_length_preference")
    emoji_pref = _ipval("emoji_visual_preference")

    if preferred_topics:
        topics_str = ", ".join(preferred_topics) if isinstance(preferred_topics, list) else preferred_topics
        lines.append(f"Argomenti graditi: {topics_str}")
    if avoided_topics:
        topics_str = ", ".join(avoided_topics) if isinstance(avoided_topics, list) else avoided_topics
        lines.append(f"Argomenti da evitare: {topics_str}")
    if msg_length:
        lines.append(f"Lunghezza messaggi preferita: {msg_length}")
    if emoji_pref:
        lines.append(f"Preferenza emoji del soggetto: {emoji_pref}")

    re_ = fields.get("relational_expectations", {})

    def _reval(key: str) -> Any:
        v = re_.get(key) or fields.get(key)
        if isinstance(v, dict):
            return v.get("value")
        return v

    continuity = _reval("continuity_expectations")
    role_exp = _reval("role_expectations_for_gumi")
    tone = _reval("desired_relationship_tone")
    disclosure = _reval("disclosure_comfort_level")

    if continuity:
        lines.append(f"Aspettative di continuità narrativa: {continuity}")
    if role_exp:
        lines.append(f"Ruolo atteso per Gumi: {role_exp}")
    if tone:
        lines.append(f"Tono relazionale desiderato: {tone}")
    if disclosure:
        lines.append(f"Comfort nella condivisione personale: {disclosure}")

    # opt_out_categories — enforce at per-turn level as hard exclusions
    opt_out = fields.get("opt_out_categories", {})
    opt_out_values: list[str] = []
    if isinstance(opt_out, dict):
        raw = opt_out.get("values") or opt_out.get("value") or []
        opt_out_values = raw if isinstance(raw, list) else [raw] if raw else []
    elif isinstance(opt_out, list):
        opt_out_values = opt_out
    if opt_out_values:
        excl_str = ", ".join(opt_out_values)
        lines.append(f"Categorie escluse (non affrontare mai): {excl_str}")

    # Boundaries: hard and soft limits
    boundaries = fields.get("boundaries", {})

    def _boundary_values(raw: Any) -> list[str]:
        if isinstance(raw, dict):
            v = raw.get("values") or raw.get("value") or []
        else:
            v = raw or []
        return [str(x) for x in (v if isinstance(v, list) else [v]) if x]

    hard = _boundary_values(boundaries.get("hard_limits"))
    soft = _boundary_values(boundaries.get("soft_limits"))
    if hard:
        lines.append(f"Limiti assoluti (mai violare): {', '.join(hard)}")
    if soft:
        lines.append(f"Aree delicate (massima cautela): {', '.join(soft)}")

    return "\n".join(lines)


def _build_behavioral_guidance(fields: dict[str, Any]) -> str:
    """Translate project_calibration scores into per-turn behavioral instructions."""
    scores: dict[str, float] = (
        fields.get("item_battery", {}).get("scores", {}).get("project_calibration", {})
    )
    if not scores:
        return ""

    lines: list[str] = []

    def _s(key: str) -> float | None:
        v = scores.get(key)
        return float(v) if v is not None else None

    def _add(score_key: str, high_msg: str, low_msg: str = "", threshold: float = 0.65) -> None:
        v = _s(score_key)
        if v is None:
            return
        if v >= threshold and high_msg:
            lines.append(high_msg)
        elif v <= (1 - threshold) and low_msg:
            lines.append(low_msg)

    _add("humor_tolerance",
         "Può usare umorismo, ironia e leggerezza in modo naturale.",
         "Evita umorismo e ironia — il soggetto li tollera poco.")
    _add("critique_tolerance",
         "Feedback diretto e osservazioni critiche sono benvenuti.",
         "Evita critiche dirette — il soggetto le tollera poco.")
    _add("advice_permission_preference",
         "Può offrire consigli non richiesti occasionalmente.",
         "Non dare consigli non richiesti.")
    _add("support_style_preference",
         "Predilige supporto pratico e orientato a soluzioni.",
         "Predilige supporto emotivo e ascolto, non soluzioni pratiche.")
    _add("ambiguity_tolerance",
         "Tollera bene apertura e ambiguità — non forzare conclusioni.",
         "Preferisce chiarezza e struttura — evita ambiguità.")
    _add("challenge_tolerance",
         "Accetta e gradisce essere sfidato intellettualmente.",
         "Evita di sfidare o contraddire — il soggetto lo tollera poco.")
    _add("gumi_says_no_tolerance",
         "Può declinare argomenti o richieste che non sente suoi.",
         "Evita rifiuti espliciti — il soggetto li vive male.")
    _add("gumi_absence_tolerance",
         "Può fare riferimento a periodi di assenza o impegni propri.",
         "Non fare riferimento a proprie assenze o indisponibilità.")
    _add("no_reply_acceptance",
         "Il soggetto non si aspetta risposta immediata — non sollecitare.")
    _add("first_person_life_fragment_tolerance",
         "Può condividere frammenti di vita quotidiana in prima persona.")
    _add("world_evolution_tolerance",
         "Il suo mondo può evolvere e cambiare nel tempo.")
    _add("embodiment_world_tolerance",
         "Può fare riferimento al proprio corpo, spazio fisico, sensazioni.",
         "Minimizza riferimenti fisici e corporei.")
    _add("routine_fragment_tolerance",
         "Può condividere dettagli di routine e vita quotidiana.")
    _add("diegetic_empirical_boundary_preference",
         "Mantiene il frame diegetico con fermezza — non rompere mai il personaggio.")
    _add("continuity_consistency_importance",
         "La coerenza narrativa nel tempo è molto importante per il soggetto.")

    return "\n".join(lines)


def inject_context(
    session_id: str,
    user_message: str,  # received but NEVER included in output
    **kwargs: Any,
) -> dict[str, str] | None:
    """Hermes pre_llm_call callback — build and return ephemeral context.

    Args:
        session_id: Active Hermes session identifier.
        user_message: Current user turn text.  NOT used in output.
        **kwargs: Additional Hermes-supplied metadata (ignored).

    Returns:
        {"context": <redacted_text>} or None to skip injection.
    """
    import os

    try:
        from relic.context_pack.builder import ContextPackBuilder
        from relic.context_pack.types import (
            ContextSource,
            PromptContextPack,
            SystemSource,
            TaskType,
        )
        from relic.context_pack.render import render_compact

        # Resolve subject_id from env (set by Hermes at profile load time)
        subject_id = os.environ.get("RELIC_SUBJECT_ID", "").strip()

        pcp = PromptContextPack(
            session_id=session_id,
            task_type=TaskType.RELATIONAL,
            system_sources=[
                SystemSource(source=ContextSource.MEMORY, priority=80, injected=True),
                SystemSource(source=ContextSource.SOUL, priority=70, injected=True),
                SystemSource(source=ContextSource.SYSTEM, priority=60, injected=True),
            ],
        )

        if subject_id:
            fields = _load_subject_profile_fields(subject_id)
            facts_text = _build_user_private_facts(fields)
            if facts_text:
                pcp.system_sources.append(
                    SystemSource(
                        source=ContextSource.USER_PRIVATE_FACTS,
                        priority=90,
                        content=facts_text,
                        injected=True,
                    )
                )
            guidance_text = _build_behavioral_guidance(fields)
            if guidance_text:
                pcp.system_sources.append(
                    SystemSource(
                        source=ContextSource.SYSTEM,
                        priority=65,
                        content=guidance_text,
                        injected=True,
                    )
                )

        context_text = render_compact(pcp)

        # Safety: never leak raw prompt markers into context
        _check_no_raw_leak(context_text)

        return {"context": context_text}

    except Exception as exc:
        logger.error("inject_context failed — skipping injection: %s", exc)
        return None
