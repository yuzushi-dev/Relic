"""Prompt context pack — multiple independent context sources.

Backward-compatible stub that imports from the new context_pack package.
"""

from __future__ import annotations

from relic.context_pack import PromptContextPack
from relic.context_pack.types import ContextSource

__all__ = ["PromptContextPack", "ContextSource"]
