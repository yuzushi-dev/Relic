"""ByteRover provider condition (PR19E).

Operational only — never relational truth. ByteRover entries describe
infrastructure / runtime telemetry; outputs are candidates for the admission
policy to evaluate, never directly relational claims about the subject.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ByteRoverCondition:
    name: str = "byterover"
    integration_class: str = "pr19-provider-evaluation"
    runtime_provider: bool = False
    operational_only: bool = True
    relational_truth: bool = False

    def describe(self) -> dict[str, str | bool]:
        return {
            "name": self.name,
            "integration_class": self.integration_class,
            "operational_only": self.operational_only,
            "relational_truth": self.relational_truth,
        }
