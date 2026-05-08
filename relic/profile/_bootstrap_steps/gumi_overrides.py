"""TUI step: collect manual or hybrid Gumi domain overrides."""
from __future__ import annotations

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


def collect_gumi_overrides(
    io_in: TextIO, io_out: TextIO, mode: str
) -> tuple[dict[str, str | None], str]:
    """Collect Gumi domain overrides and agent name for manual/hybrid generation modes.

    Returns:
        (domain_overrides, agent_name)
    """
    if mode == "random":
        return {}, "Gumi"
    print("\n--- Gumi Profile Overrides ---", file=io_out)
    agent_name = (
        prompt_optional("name", "Agent name.", io_in, io_out, default="Gumi") or "Gumi"
    )
    required = mode == "manual"
    result: dict[str, str | None] = {}
    for domain in DOMAINS:
        description = f"Override for Gumi domain '{domain}'."
        if required:
            result[domain] = prompt_required(domain, description, io_in, io_out)
        else:
            value = prompt_optional(domain, description, io_in, io_out)
            if value is not None:
                result[domain] = value
    return result, agent_name
