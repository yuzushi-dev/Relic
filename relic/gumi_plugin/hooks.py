"""Hermes lifecycle hooks (PR22E)."""
from __future__ import annotations

from typing import Any, Callable

PRE_LLM_CALL = "pre_llm_call"
POST_LLM_CALL = "post_llm_call"
PRE_TOOL_CALL = "pre_tool_call"

_REGISTERED: dict[str, list[Callable[..., Any]]] = {}


def register(event: str, handler: Callable[..., Any]) -> None:
    _REGISTERED.setdefault(event, []).append(handler)


def dispatch(event: str, payload: dict[str, Any]) -> list[Any]:
    out: list[Any] = []
    for h in _REGISTERED.get(event, []):
        try:
            out.append(h(payload))
        except Exception as exc:  # fail-closed: never propagate
            out.append({"error": str(exc), "fail_closed": True})
    return out


def reset() -> None:
    _REGISTERED.clear()
