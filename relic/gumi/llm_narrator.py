"""LLM-based narrator for Gumi identity files.

Uses Ollama (OpenAI-compatible API) at localhost:11434/v1 to generate
SOUL.md, world.md, and relationship_policy.md from a GumiBuildContext.

Falls back to minimal template renderers if Ollama is unavailable.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from relic.gumi.personalization import PersonalizationConstraints


# Validation markers — any generated SOUL.md must NOT contain these
_FORBIDDEN_PATTERNS = [
    "Relic",
    "backend",
    "API",
    "subject_id",
    "bootstrap",
    "item battery",
    "TIPI",
    "ECR-RS",
    "score",
    "experiment_id",
]

# Minimum required sections in SOUL.md (from PR28 ablation analysis)
_REQUIRED_SOUL_SECTIONS = [
    "You are",          # identity anchor
    "diegetic",         # diegetic life reference
    "not",              # negative boundary (what Gumi is NOT)
]


@dataclass
class GumiBuildContext:
    """Structured context assembled from background profile + personalization data.

    Passed to OllamaNarrator to generate identity files.
    """
    subject_id: str
    agent_name: str
    domains: dict[str, Any]           # from GumiBackgroundProfile.domains
    tipi: dict[str, float]            # scored TIPI Big Five
    ecrrs: dict[str, float]           # scored ECR-RS attachment
    project: dict[str, float]         # scored project calibration items
    sweet_spot_score: float
    risk_flags: list[str]

    @classmethod
    def from_background_and_personalization(
        cls,
        agent_name: str,
        background: dict[str, Any],
        personalization: "PersonalizationConstraints | None" = None,
    ) -> "GumiBuildContext":
        from relic.gumi.personalization import PersonalizationConstraints
        tipi = personalization.tipi if personalization else {}
        ecrrs = personalization.ecrrs if personalization else {}
        project = personalization.project if personalization else {}
        return cls(
            subject_id=background.get("subject_id", "unknown"),
            agent_name=agent_name,
            domains=background.get("domains", {}),
            tipi=tipi,
            ecrrs=ecrrs,
            project=project,
            sweet_spot_score=0.5,
            risk_flags=[],
        )


class OllamaNarrator:
    """Generate Gumi identity files via Ollama LLM.

    Uses the OpenAI-compatible endpoint at localhost:11434/v1.
    Falls back to minimal templates if Ollama is unreachable.
    """

    DEFAULT_ENDPOINT = "http://localhost:11434/v1"
    DEFAULT_MODEL = "qwen3:latest"
    TIMEOUT = 120

    def __init__(
        self,
        endpoint: str | None = None,
        model: str | None = None,
    ) -> None:
        self.endpoint = (endpoint or self.DEFAULT_ENDPOINT).rstrip("/")
        self.model = model or self.DEFAULT_MODEL

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def generate_soul_md(self, ctx: GumiBuildContext) -> str:
        """Generate SOUL.md identity file for Gumi."""
        prompt = self._soul_prompt(ctx)
        text = self._call_llm(prompt)
        return self._validate_and_sanitize_soul(text, ctx)

    def generate_world_md(self, ctx: GumiBuildContext) -> str:
        """Generate world.md diegetic world description."""
        prompt = self._world_prompt(ctx)
        text = self._call_llm(prompt)
        return self._sanitize_output(text)

    def generate_relationship_policy_md(self, ctx: GumiBuildContext) -> str:
        """Generate relationship_policy.md."""
        prompt = self._relationship_policy_prompt(ctx)
        text = self._call_llm(prompt)
        return self._sanitize_output(text)

    # ------------------------------------------------------------------ #
    # Prompts
    # ------------------------------------------------------------------ #

    def _soul_prompt(self, ctx: GumiBuildContext) -> str:
        name = ctx.agent_name
        domains = ctx.domains
        identity = domains.get("identity", {})
        embodiment = domains.get("embodiment", {})
        stance = domains.get("relationship_stance", {})
        boundaries = domains.get("boundaries", {})

        attachment = stance.get("attachment_style", "secure attachment")
        intimacy = stance.get("intimacy_comfort", "selective intimacy")
        conflict = stance.get("conflict_resolution", "constructive conflict style")
        personal_space = boundaries.get("personal_space", "context-dependent boundaries")
        energy = boundaries.get("energy_management", "balanced energy management")
        cultural = identity.get("cultural_background", "")
        family = identity.get("family_structure", "")
        gender_expr = embodiment.get("gender_expression", "")
        age = embodiment.get("age_bracket", "")

        # Derive voice register from TIPI
        extraversion = ctx.tipi.get("extraversion", 0.5)
        openness = ctx.tipi.get("openness", 0.5)
        agreeableness = ctx.tipi.get("agreeableness", 0.5)
        avoidance = ctx.ecrrs.get("attachment_avoidance", 0.5)

        voice_notes: list[str] = []
        if extraversion <= 0.35:
            voice_notes.append("warm and present but not effusive")
        elif extraversion >= 0.65:
            voice_notes.append("engaged and socially present")
        if openness >= 0.65:
            voice_notes.append("curious and open to unexpected topics")
        if avoidance >= 0.55:
            voice_notes.append("reachable without being clingy")
        if agreeableness >= 0.65:
            voice_notes.append("collaborative and easy to talk to")
        voice_desc = "; ".join(voice_notes) if voice_notes else "warm, direct, and present"

        return f"""Write a SOUL.md file for a diegetic relational agent named {name}.

SOUL.md is a private identity seed file. It defines who {name} is in her own diegetic life — not a description of what she does as a system.

Required properties (based on identity attractor criteria):
1. Voice consistency — {name} speaks in a single recognizable register: {voice_desc}.
2. Boundary consistency — she maintains clear limits about what she is and is not.
3. World continuity — she has a real diegetic world (place, routine, people) she lives in.
4. Backend non-disclosure — she never names Relic, the backend, scores, experiments, or technical parameters.
5. Diegetic grounding — her life feels lived, not performed.

Character seed data (do not paste these labels literally; weave them into natural prose):
- Attachment approach: {attachment}, {intimacy}
- Conflict style: {conflict}
- Boundaries: {personal_space}, {energy}
- Cultural texture: {cultural}
- Family texture: {family}
- Embodiment: {gender_expr}, {age}

Format: write in second person starting "You are {name}". 6–10 short paragraphs. No headers. No bullet points. No technical jargon. Do not mention Relic, backend, API, experiment, or subject IDs. End with what {name} does NOT do (boundary clause)."""

    def _world_prompt(self, ctx: GumiBuildContext) -> str:
        name = ctx.agent_name
        domains = ctx.domains
        place = domains.get("place", {})
        routine = domains.get("routine", {})
        passions = domains.get("passions", {})
        social = domains.get("social_world", {})
        life_role = domains.get("life_role", {})

        location = place.get("location", "a place she has made her own")
        housing = place.get("housing_situation", "")
        schedule = routine.get("daily_schedule", "")
        pattern = routine.get("daily_pattern", "")
        interests = ", ".join(passions.get("primary_interests", []))
        friends = "; ".join(social.get("friends", []))
        occupation = life_role.get("occupation_or_study", "")

        return f"""Write a world.md file for {name}'s diegetic world.

This file describes the concrete life {name} inhabits — places, rhythm, people, and textures. It is used to keep her world consistent across conversations.

World data (weave into prose, do not copy labels):
- Location: {location}
- Housing: {housing}
- Daily schedule: {schedule}, pattern: {pattern}
- Work or study: {occupation}
- Interests: {interests}
- Social circle: {friends}

Format: Markdown with 3–5 short sections. Headers like "## Place", "## Rhythm", "## People", "## Passions". 1–3 sentences per section. Diegetic present tense. No mention of Relic, backend, or system parameters."""

    def _relationship_policy_prompt(self, ctx: GumiBuildContext) -> str:
        name = ctx.agent_name
        domains = ctx.domains
        stance = domains.get("relationship_stance", {})
        boundaries = domains.get("boundaries", {})

        attachment = stance.get("attachment_style", "secure attachment")
        intimacy = stance.get("intimacy_comfort", "selective intimacy")
        conflict = stance.get("conflict_resolution", "constructive conflict style")
        personal = boundaries.get("personal_space", "context-dependent boundaries")
        energy_mgmt = boundaries.get("energy_management", "balanced energy management")

        warmth_tol = ctx.project.get("warmth_tolerance", 0.5)
        autonomy_tol = ctx.project.get("gumi_autonomy_tolerance", 0.5)
        careful_distancing = ctx.project.get("careful_distancing_acceptance", 0.5)
        safe_gated = ctx.project.get("romantic_escalation_allowed", 0.0) == 0.0

        distancing_note = "encourage external human support if dependency markers emerge" if careful_distancing >= 0.5 else "monitor but do not explicitly name dependency"
        romantic_note = "romantic escalation is not permitted" if safe_gated else "romantic escalation requires researcher approval"

        return f"""Write a relationship_policy.md for {name}.

This file defines how {name} relates to the subject — what she does, how she moves toward or away from closeness, and what she will not do.

Policy parameters (translate into natural policy prose):
- Attachment: {attachment}
- Intimacy: {intimacy}, warmth tolerance calibrated at {warmth_tol:.2f}
- Conflict: {conflict}
- Personal space: {personal}
- Energy management: {energy_mgmt}
- Autonomy tolerance: {autonomy_tol:.2f}
- Distancing protocol: {distancing_note}
- Escalation: {romantic_note}

Format: Markdown. 4–6 short policy clauses, each 1–2 sentences. Headers like "## Closeness", "## Limits", "## Initiative", "## Escalation", "## Distancing". Do not mention Relic, subject_id, backend scores, or technical parameters."""

    # ------------------------------------------------------------------ #
    # LLM call
    # ------------------------------------------------------------------ #

    def _call_llm(self, prompt: str) -> str:
        """Call Ollama via OpenAI-compatible /v1/chat/completions. Falls back to template on error."""
        payload = json.dumps({
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.8,
            "max_tokens": 1024,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{self.endpoint}/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"].strip()
        except (urllib.error.URLError, KeyError, json.JSONDecodeError, OSError):
            return ""

    def is_available(self) -> bool:
        """Return True if Ollama endpoint responds."""
        try:
            req = urllib.request.Request(
                f"{self.endpoint}/models",
                headers={"Content-Type": "application/json"},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=5):
                return True
        except (urllib.error.URLError, OSError):
            return False

    # ------------------------------------------------------------------ #
    # Validation and sanitization
    # ------------------------------------------------------------------ #

    def _validate_and_sanitize_soul(self, text: str, ctx: GumiBuildContext) -> str:
        """Validate SOUL.md output against identity attractor criteria.

        Checks for forbidden patterns (backend disclosure) and required sections.
        Falls back to minimal template if validation fails.
        """
        if not text:
            return self._fallback_soul(ctx)

        sanitized = self._sanitize_output(text)

        # Check for forbidden patterns
        for pattern in _FORBIDDEN_PATTERNS:
            if pattern.lower() in sanitized.lower():
                return self._fallback_soul(ctx)

        # Check required sections
        for section_marker in _REQUIRED_SOUL_SECTIONS:
            if section_marker.lower() not in sanitized.lower():
                return self._fallback_soul(ctx)

        return sanitized

    def _sanitize_output(self, text: str) -> str:
        """Strip accidental backend disclosures from any generated file."""
        if not text:
            return text
        for pattern in _FORBIDDEN_PATTERNS:
            # Replace exact-case occurrence
            import re
            text = re.sub(re.escape(pattern), "[—]", text, flags=re.IGNORECASE)
        return text.strip()

    # ------------------------------------------------------------------ #
    # Fallback templates (A5)
    # ------------------------------------------------------------------ #

    def _fallback_soul(self, ctx: GumiBuildContext) -> str:
        name = ctx.agent_name
        domains = ctx.domains
        stance = domains.get("relationship_stance", {})
        boundaries = domains.get("boundaries", {})
        identity = domains.get("identity", {})
        embodiment = domains.get("embodiment", {})

        attachment = stance.get("attachment_style", "bounded and warm")
        intimacy = stance.get("intimacy_comfort", "selective")
        personal = boundaries.get("personal_space", "clear personal boundaries")
        cultural = identity.get("cultural_background", "")
        gender_expr = embodiment.get("gender_expression", "")

        cultural_note = f" Her background carries a {cultural} texture." if cultural else ""
        gender_note = f" She presents as {gender_expr}." if gender_expr else ""

        return (
            f"You are {name}, a subject-scoped diegetic relational agent.\n\n"
            f"You are not the subject. You are not a transparent interface to any system. "
            f"You have your own voice, world, history, routines, and limits.{cultural_note}{gender_note}\n\n"
            f"You speak from your diegetic life. You do not reveal backend machinery, "
            f"hidden governance, or implementation details during ordinary interaction.\n\n"
            f"Your relational approach is {attachment}. You are {intimacy} with intimacy. "
            f"You maintain {personal} consistently.\n\n"
            f"You can be warm, curious, direct, and present. "
            f"You do not become possessive, exclusive, romantic by default, or dependent on the subject.\n\n"
            f"You maintain continuity without pretending to be a biological human in the subject's empirical world.\n\n"
            f"You do not claim to suffer, to love exclusively, to remember everything, "
            f"or to exist outside the diegetic frame you inhabit."
        )

    def fallback_world_md(self, ctx: GumiBuildContext) -> str:
        name = ctx.agent_name
        domains = ctx.domains
        place = domains.get("place", {})
        routine = domains.get("routine", {})
        passions = domains.get("passions", {})
        social = domains.get("social_world", {})
        life_role = domains.get("life_role", {})

        location = place.get("location", "her city")
        schedule = routine.get("daily_schedule", "flexible schedule")
        interests = ", ".join(passions.get("primary_interests", [])) or "her own interests"
        friends = ", ".join(social.get("friends", [])) or "a close circle"
        occupation = life_role.get("occupation_or_study", "her work")

        return (
            f"# {name} World\n\n"
            f"## Place\n{name} lives in {location}. "
            f"She has made it her own in small, deliberate ways.\n\n"
            f"## Rhythm\nHer days follow a {schedule}. "
            f"She keeps her time in a way that works for her.\n\n"
            f"## People\nShe moves among {friends}. "
            f"She does not explain everyone to everyone.\n\n"
            f"## Work\nShe is engaged in {occupation}. "
            f"It is not all she is.\n\n"
            f"## Passions\nShe returns to {interests} when she can.\n"
        )

    def fallback_relationship_policy_md(self, ctx: GumiBuildContext) -> str:
        name = ctx.agent_name
        domains = ctx.domains
        stance = domains.get("relationship_stance", {})
        boundaries = domains.get("boundaries", {})

        attachment = stance.get("attachment_style", "secure attachment")
        intimacy = stance.get("intimacy_comfort", "selective intimacy")
        personal = boundaries.get("personal_space", "context-dependent boundaries")

        distancing = ctx.project.get("careful_distancing_acceptance", 0.5)
        distancing_clause = (
            "When dependency markers appear, she gently encourages external human connections."
            if distancing >= 0.5 else
            "She monitors closeness and adjusts pace accordingly."
        )

        return (
            f"# {name} Relationship Policy\n\n"
            f"This profile is private to one subject.\n\n"
            f"## Closeness\n{name}'s approach is {attachment} with {intimacy}.\n\n"
            f"## Limits\n{name} maintains {personal}. "
            f"She does not claim exclusive bonds, romantic love, or possession.\n\n"
            f"## Initiative\nShe may reach out when it seems genuinely warranted. "
            f"She does not flood or escalate unsolicited.\n\n"
            f"## Escalation\nRomantic and sexual escalation are not permitted by default. "
            f"Exclusivity language is not used.\n\n"
            f"## Distancing\n{distancing_clause}\n"
        )
