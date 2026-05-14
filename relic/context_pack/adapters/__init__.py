"""Context pack adapters for external decision sources.

This module provides adapters to convert decisions from various
sources (CAC, Continuity, etc.) into PromptContextPack memory candidates.
"""

from relic.context_pack.adapters.cac import CACContextPackAdapter
from relic.context_pack.adapters.continuity import (
    ContinuityContextPackAdapter,
    get_continuity_context_pack_adapter,
)

__all__ = [
    "CACContextPackAdapter",
    "ContinuityContextPackAdapter",
    "get_continuity_context_pack_adapter",
]
