"""Context pack builder - Builds PromptContextPack from CAC decisions.

This module provides the builder pattern for constructing
PromptContextPack instances from CAC-adjudicated memory candidates.

CAC becomes the ONLY path by which memory candidates are admitted
into injected runtime context.
"""

from __future__ import annotations

import logging
from dataclasses import field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from relic.context_pack.adapters.cac import CACContextPackAdapter, CACContextPackAdapterResult
from relic.context_pack.types import (
    MemoryCandidate,
    BlockedItem,
    PromptContextPack,
    TaskType,
    RoleplayLevel,
)
from relic.cac.types import CACInput, CACDecisionResult

try:
    import structlog
    logger = structlog.get_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)


class ContextPackBuilder:
    """Builder for PromptContextPack from CAC decisions.
    
    This builder enforces that CAC is the ONLY path for memory
    candidates to enter runtime context.
    """

    def __init__(
        self,
        adapter: CACContextPackAdapter | None = None,
        session_id: str | None = None,
        task_type: TaskType = TaskType.FACTUAL,
    ):
        self._adapter = adapter or CACContextPackAdapter()
        self._session_id = session_id
        self._task_type = task_type
        self._memory_candidates: list[MemoryCandidate] = []
        self._blocked_items: list[BlockedItem] = []
        self._admitted_count = 0
        self._blocked_count = 0

    def add_cac_decision(
        self,
        inp: CACInput,
        result: CACDecisionResult,
    ) -> "ContextPackBuilder":
        """Add a CAC decision to the context pack.
        
        Args:
            inp: CAC input
            result: CAC decision result
            
        Returns:
            Self for chaining
        """
        adapt_result = self._adapter.adapt(inp, result)

        # Add admitted candidates
        for candidate in adapt_result.candidates:
            self._memory_candidates.append(candidate)
            self._admitted_count += 1
            logger.debug("context_pack_injected",
                        memory_id=candidate.candidate_id,
                        decision=candidate.metadata.get("decision"))

        # Add blocked items
        for blocked in adapt_result.blocked:
            self._blocked_items.append(blocked)
            self._blocked_count += 1
            logger.debug("context_pack_blocked",
                        memory_id=blocked.item_id,
                        reason=blocked.reason)

        return self

    def add_cac_decisions(
        self,
        decisions: list[tuple[CACInput, CACDecisionResult]],
    ) -> "ContextPackBuilder":
        """Add multiple CAC decisions to the context pack.
        
        Args:
            decisions: List of (CACInput, CACDecisionResult) tuples
            
        Returns:
            Self for chaining
        """
        for inp, result in decisions:
            self.add_cac_decision(inp, result)
        return self

    def build(self) -> PromptContextPack:
        """Build the final PromptContextPack.
        
        Returns:
            Complete PromptContextPack with all injected and blocked contexts
        """
        return PromptContextPack(
            session_id=self._session_id,
            created_at=datetime.now(timezone.utc),
            task_type=self._task_type,
            memory_candidates=self._memory_candidates.copy(),
            blocked_items=self._blocked_items.copy(),
        )

    def reset(self) -> "ContextPackBuilder":
        """Reset the builder state.
        
        Returns:
            Self for chaining
        """
        self._memory_candidates.clear()
        self._blocked_items.clear()
        self._admitted_count = 0
        self._blocked_count = 0
        return self

    @property
    def admitted_count(self) -> int:
        """Get count of admitted contexts."""
        return self._admitted_count

    @property
    def blocked_count(self) -> int:
        """Get count of blocked contexts."""
        return self._blocked_count


def create_context_pack_from_cac(
    inputs: list[tuple[CACInput, CACDecisionResult]],
    session_id: str | None = None,
    task_type: TaskType = TaskType.FACTUAL,
) -> PromptContextPack:
    """Create a PromptContextPack from CAC decisions.
    
    Convenience function that creates a builder, adds all decisions,
    and returns the built context pack.
    
    Args:
        inputs: List of (CACInput, CACDecisionResult) tuples
        session_id: Optional session ID
        task_type: Task type for the context pack
        
    Returns:
        Complete PromptContextPack
    """
    builder = ContextPackBuilder(session_id=session_id, task_type=task_type)
    builder.add_cac_decisions(inputs)
    return builder.build()
