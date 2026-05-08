"""Prompt context pack — multiple independent context sources."""

from __future__ import annotations

from relic.hermes_plugin.context_injection import ContextSource


class PromptContextPack:
    """Context pack with independent sources. Never monolithic."""

    def get_context_sources(self) -> list[ContextSource]:
        return [
            ContextSource.MEMORY,
            ContextSource.USER,
            ContextSource.SYSTEM,
            ContextSource.SKILL,
        ]
