"""TUI step: review generated Gumi background."""
from __future__ import annotations

from typing import Literal, TextIO

_DOMAINS = [
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


def _short_lines(value: object) -> list[str]:
    text = value if isinstance(value, str) else repr(value)
    lines = text.splitlines() or [text]
    if len(lines) > 5:
        return lines[:5] + ["..."]
    return lines


def review_gumi_background(io_in: TextIO, io_out: TextIO, gumi_profile_dict: dict) -> Literal["accept", "regenerate", "abort"]:
    """Render the nine Gumi domains and ask for a researcher decision."""
    print("\n--- Gumi Profile Review ---", file=io_out)
    domains = gumi_profile_dict.get("domains", gumi_profile_dict)
    for domain in _DOMAINS:
        print(f"\n[{domain}]", file=io_out)
        for line in _short_lines(domains.get(domain, {})):
            print(f"  {line}", file=io_out)
    while True:
        print("\nAzione: accept | regenerate | abort", file=io_out)
        raw = io_in.readline()
        action = raw.strip().lower() if raw else "abort"
        if action in {"accept", "regenerate", "abort"}:
            return action  # type: ignore[return-value]
        print("Invalid choice.", file=io_out)
