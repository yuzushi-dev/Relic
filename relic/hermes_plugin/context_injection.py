"""Context injection sources for Hermes plugin."""

from __future__ import annotations

from enum import Enum


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
