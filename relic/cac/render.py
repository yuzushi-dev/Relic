"""CAC render - Output rendering for memory decisions.

This module handles rendering memory decisions for injection.
NEVER renders disputed hints - they are always blocked.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from relic.cac.types import (
    CACDecision,
    CACDecisionResult,
    CACInput,
    SeverityClass,
)

try:
    import structlog
    logger = structlog.get_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)


@dataclass
class RenderResult:
    """Result of rendering a memory decision."""
    should_inject: bool
    content: str | None  # Rendered content if injection allowed
    decision: CACDecision
    severity: SeverityClass
    warning_message: str | None = None
    metadata: dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class CACRenderer:
    """Renders memory decisions for output/injection.

    Key rules:
    - Disputed hints NEVER render (hard block)
    - Quarantined memory has zero runtime influence
    - S1 memories cannot influence PromptContextPack
    """

    def render(self, inp: CACInput, result: CACDecisionResult) -> RenderResult:
        """Render a CAC decision for injection.

        Returns RenderResult with:
        - should_inject: Whether to inject
        - content: Rendered content if injection allowed
        - warning_message: Any warnings for admitted memories

        Block conditions:
        - Disputed hints never render
        - S0 memories never render
        - S1 quarantined memories never render
        """
        # Hard block: disputed hints never render
        if inp.disputed:
            logger.info("render_blocked_disputed",
                       memory_id=inp.memory_id,
                       dispute_reason=inp.dispute_reason)
            return RenderResult(
                should_inject=False,
                content=None,
                decision=result.decision,
                severity=result.severity,
                warning_message="Disputed memory blocked from rendering",
                metadata={"blocked_reason": "disputed"},
            )

        # Block: S0 severity
        if result.severity == SeverityClass.S0:
            logger.info("render_blocked_s0",
                       memory_id=inp.memory_id,
                       skip_reason=result.skip_reason)
            return RenderResult(
                should_inject=False,
                content=None,
                decision=result.decision,
                severity=result.severity,
                warning_message=f"S0 blocked: {result.skip_reason}",
                metadata={"blocked_reason": "s0"},
            )

        # Block: S1 quarantined memory (zero runtime influence)
        if result.decision == CACDecision.QUARANTINED:
            logger.info("render_blocked_quarantined",
                       memory_id=inp.memory_id,
                       quarantine_until=result.quarantine_until)
            return RenderResult(
                should_inject=False,
                content=None,
                decision=result.decision,
                severity=result.severity,
                warning_message="Quarantined memory has zero runtime influence",
                metadata={
                    "blocked_reason": "quarantine",
                    "quarantine_until": result.quarantine_until.isoformat() if result.quarantine_until else None,
                },
            )

        # Block: Deferred decisions
        if result.decision == CACDecision.DEFERRED:
            logger.info("render_blocked_deferred",
                       memory_id=inp.memory_id,
                       deferred_reason=result.deferred_reason)
            return RenderResult(
                should_inject=False,
                content=None,
                decision=result.decision,
                severity=result.severity,
                warning_message=f"Deferred: {result.deferred_reason}",
                metadata={"blocked_reason": "deferred"},
            )

        # Block: No memory content
        if not inp.memory_content:
            logger.debug("render_no_memory", memory_id=inp.memory_id)
            return RenderResult(
                should_inject=False,
                content=None,
                decision=CACDecision.NONE,
                severity=SeverityClass.NONE,
                warning_message=None,
                metadata={"blocked_reason": "no_content"},
            )

        # Admitted decisions - render content
        if result.decision == CACDecision.NONE:
            # No memory to inject
            return RenderResult(
                should_inject=False,
                content=None,
                decision=CACDecision.NONE,
                severity=SeverityClass.NONE,
                warning_message=None,
                metadata={},
            )

        if result.decision == CACDecision.COMPACT:
            # Compact representation
            rendered = self._compact_render(inp.memory_content)
            return RenderResult(
                should_inject=True,
                content=rendered,
                decision=CACDecision.COMPACT,
                severity=result.severity,
                warning_message=None,
                metadata={"render_mode": "compact"},
            )

        if result.decision == CACDecision.EXPANDED:
            # Full content
            return RenderResult(
                should_inject=True,
                content=inp.memory_content,
                decision=CACDecision.EXPANDED,
                severity=result.severity,
                warning_message=result.warning_message,
                metadata={"render_mode": "expanded"},
            )

        if result.decision == CACDecision.LOCAL_ONLY:
            # Local context only
            return RenderResult(
                should_inject=True,
                content=inp.memory_content,
                decision=CACDecision.LOCAL_ONLY,
                severity=result.severity,
                warning_message=None,
                metadata={"render_mode": "local_only", "context_restricted": True},
            )

        # Fallback - block
        return RenderResult(
            should_inject=False,
            content=None,
            decision=result.decision,
            severity=result.severity,
            warning_message="Unknown decision type",
            metadata={"blocked_reason": "unknown_decision"},
        )

    def _compact_render(self, content: str, max_length: int = 200) -> str:
        """Create compact representation of memory content."""
        if len(content) <= max_length:
            return content

        # Truncate with indicator
        return content[:max_length].rsplit(" ", 1)[0] + "..."

    def render_for_context_pack(
        self,
        inp: CACInput,
        result: CACDecisionResult,
    ) -> tuple[bool, str | None, dict]:
        """Render for PromptContextPack integration.

        Returns (allowed, content, metadata) tuple.
        S1 quarantined memory returns (False, None, metadata).
        """
        render_result = self.render(inp, result)

        # S1 quarantined memory has ZERO runtime influence on PromptContextPack
        if result.severity == SeverityClass.S1 or result.decision == CACDecision.QUARANTINED:
            return False, None, {
                "quarantined": True,
                "zero_runtime_influence": True,
                "memory_id": inp.memory_id,
                "quarantine_until": result.quarantine_until.isoformat() if result.quarantine_until else None,
            }

        return (
            render_result.should_inject,
            render_result.content,
            render_result.metadata,
        )
