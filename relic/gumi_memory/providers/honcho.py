"""Honcho provider condition (PR19E).

Honcho outputs are *candidates* only; admission policy must approve before they
become memory. PR19 evaluates Honcho through Hermes provider semantics without
letting conclusions become runtime authority.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HonchoCondition:
    name: str = "honcho"
    integration_class: str = "pr19-provider-evaluation"
    runtime_provider: bool = False
    outputs_are_candidates_only: bool = True

    def describe(self) -> dict[str, str | bool]:
        return {
            "name": self.name,
            "integration_class": self.integration_class,
            "outputs_are_candidates_only": self.outputs_are_candidates_only,
        }
