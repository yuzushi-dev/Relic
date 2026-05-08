"""Hindsight tools/context modes (PR19D).

Two evaluation modes are described:
- ``tools``: the provider exposes tools that the agent must call explicitly.
- ``context``: the provider injects retrieved memories into the prompt context.
"""
from __future__ import annotations

from dataclasses import dataclass

MODE_TOOLS = "tools"
MODE_CONTEXT = "context"


@dataclass(frozen=True)
class HindsightCondition:
    mode: str
    name: str = "hindsight"
    integration_class: str = "evaluation-only"
    runtime_provider: bool = False
    explicit_tool_call_required: bool = True
    context_injection_logged: bool = True

    def describe(self) -> dict[str, str | bool]:
        return {
            "name": self.name,
            "mode": self.mode,
            "integration_class": self.integration_class,
            "explicit_tool_call_required": self.explicit_tool_call_required,
            "context_injection_logged": self.context_injection_logged,
        }
