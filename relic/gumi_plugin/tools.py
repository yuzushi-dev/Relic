"""Tool surface exposed by the Gumi plugin (PR22E).

Tools are read-only by default; mutating tools must be opted-in via config.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GumiTool:
    name: str
    description: str
    mutating: bool = False
    permissions: tuple[str, ...] = field(default_factory=tuple)


READONLY_TOOLS: tuple[GumiTool, ...] = (
    GumiTool("gumi.recall", "Read continuity diary entry", mutating=False),
    GumiTool("gumi.snapshot", "Return current world-state snapshot", mutating=False),
)

MUTATING_TOOLS: tuple[GumiTool, ...] = (
    GumiTool(
        "gumi.write_diary",
        "Append diary entry (admission policy required)",
        mutating=True,
        permissions=("diary:write", "admission:approved"),
    ),
)


def all_tools(*, allow_mutating: bool = False) -> tuple[GumiTool, ...]:
    return READONLY_TOOLS + (MUTATING_TOOLS if allow_mutating else tuple())
