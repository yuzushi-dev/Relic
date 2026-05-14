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
    try:
        from relic.context_pack.builder import PCPBuilder, TaskType, ContinuityMode, RoleplayLevel

        builder = PCPBuilder(fail_safe=None, trace=None)
        pcp = builder.build(
            session_id=session_id,
            task_type=TaskType.TECHNICAL,
            roleplay_level=RoleplayLevel.OFF,
            continuity_mode=ContinuityMode.COMPACT,
        )
        if pcp is None:
            return None

        context_text = pcp.redacted_text if hasattr(pcp, "redacted_text") else str(pcp.to_dict())

        # Safety: never leak raw prompt markers into context
        _check_no_raw_leak(context_text)

        return {"context": context_text}

    except Exception as exc:
        logger.error("inject_context failed — skipping injection: %s", exc)
        return None
