"""Holographic baseline provider stub (PR19C).

Reference-only: outputs are evaluation candidates, never runtime memory.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HolographicCondition:
    name: str = "holographic"
    integration_class: str = "evaluation-only"
    runtime_provider: bool = False

    def describe(self) -> dict[str, str]:
        return {
            "name": self.name,
            "integration_class": self.integration_class,
            "purpose": "baseline density / pattern completion comparison",
        }
