"""CAC controller - Main entry point for the Correction/Admission/Compliance gate.

This module coordinates the CAC pipeline:
1. Receive CACInput (memory to evaluate)
2. Score severity using CACScorer
3. Determine decision using scoring rules
4. Write audit trace to cac_trace.jsonl
5. Return decision result

Key guarantees:
- Every decision writes to cac_trace.jsonl
- Raw session text never appears in traces
- Disputed hints are always blocked
- S1 quarantined memory has zero runtime influence
- CAC does NOT import compiler or lab modules
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime
from pathlib import Path

from relic.cac.render import CACRenderer, RenderResult
from relic.cac.scoring import CACScorer
from relic.cac.trace import CACTraceWriter
from relic.cac.types import (
    CACContext,
    CACDecision,
    CACDecisionResult,
    CACInput,
    CACTrace,
    MemorySource,
    SeverityClass,
)

try:
    import structlog
    logger = structlog.get_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)


class CACController:
    """Main controller for the CAC (Correction/Admission/Compliance) gate.

    This is the central coordinator for memory decisions. It:
    1. Receives memory inputs for evaluation
    2. Applies scoring and classification rules
    3. Writes audit traces for every decision
    4. Returns decision results for runtime use

    IMPORTANT: This controller does NOT import from relic.compiler or relic.lab
    to maintain strict isolation and avoid side-channel data flow.
    """

    def __init__(
        self,
        trace_path: Path | str | None = None,
        scorer: CACScorer | None = None,
        trace_writer: CACTraceWriter | None = None,
        renderer: CACRenderer | None = None,
    ):
        self._scorer = scorer or CACScorer()
        self._trace_writer = trace_writer or CACTraceWriter(trace_path)
        self._renderer = renderer or CACRenderer()

    def evaluate(self, inp: CACInput, context: CACContext | None = None) -> CACDecisionResult:
        """Evaluate a memory input and return a CAC decision.

        This is the main entry point for the CAC gate. It:
        1. Scores the memory severity
        2. Determines the decision
        3. Computes skip reason if needed
        4. Writes trace to cac_trace.jsonl
        5. Returns the decision result

        Args:
            inp: CACInput containing memory to evaluate
            context: Optional evaluation context

        Returns:
            CACDecisionResult with decision, severity, and skip_reason
        """
        logger.debug("cac_evaluate",
                    memory_id=inp.memory_id,
                    source=inp.source.value,
                    disputed=inp.disputed)

        # Step 1: Score severity
        scoring = self._scorer.score(inp)

        # Step 2: Determine decision
        decision = self._scorer.determine_decision(inp, scoring)

        # Step 3: Compute skip reason for non-admission decisions
        skip_reason = self._scorer.compute_skip_reason(inp, scoring, decision)

        # Step 4: Build result
        memory_hash = inp.memory_hash or self._compute_hash(inp.memory_content or "")

        result = CACDecisionResult(
            decision=decision,
            severity=scoring.severity,
            memory_id=inp.memory_id,
            memory_hash=memory_hash,
            skip_reason=skip_reason,
            deferred_reason=inp.metadata.get("defer_reason") if decision == CACDecision.DEFERRED else None,
            quarantine_until=self._compute_quarantine_time(scoring, decision),
            warning_message=self._compute_warning(scoring, decision),
            metadata={
                "confidence": scoring.confidence,
                "factors": scoring.factors,
                "evaluation_mode": context.evaluation_mode if context else "standard",
            },
        )

        # Step 5: Write trace BEFORE returning (audit guarantee)
        self._write_trace(inp, result, context)

        logger.info("cac_decision",
                   memory_id=inp.memory_id,
                   decision=decision.value,
                   severity=scoring.severity.value)

        return result

    def evaluate_batch(self, inputs: list[CACInput], context: CACContext | None = None) -> list[CACDecisionResult]:
        """Evaluate multiple memory inputs.

        Each input is evaluated independently and all traces are written.
        """
        results = []
        for inp in inputs:
            result = self.evaluate(inp, context)
            results.append(result)
        return results

    def render(self, inp: CACInput, result: CACDecisionResult) -> RenderResult:
        """Render a decision for injection/use.

        This wraps the renderer with CAC-specific logic.
        """
        return self._renderer.render(inp, result)

    def render_for_context_pack(
        self,
        inp: CACInput,
        result: CACDecisionResult,
    ) -> tuple[bool, str | None, dict]:
        """Render for PromptContextPack with S1 quarantine enforcement.

        Returns (allowed, content, metadata) where allowed=False and
        content=None for S1 quarantined memory.
        """
        return self._renderer.render_for_context_pack(inp, result)

    def get_traces(self) -> list[CACTrace]:
        """Get all CAC traces from the trace file."""
        return self._trace_writer.read_all()

    def clear_traces(self) -> None:
        """Clear all traces (for testing)."""
        self._trace_writer.clear()

    def _write_trace(self, inp: CACInput, result: CACDecisionResult, context: CACContext | None) -> None:
        """Write a trace entry for the decision."""
        trace = CACTrace(
            trace_id=str(uuid.uuid4()),
            memory_id=inp.memory_id,
            memory_hash=result.memory_hash,
            source=inp.source.value if isinstance(inp.source, MemorySource) else str(inp.source),
            decision=result.decision.value if isinstance(result.decision, CACDecision) else str(result.decision),
            severity=result.severity.value if isinstance(result.severity, SeverityClass) else str(result.severity),
            disputed=inp.disputed,
            skip_reason=result.skip_reason,
            deferred_reason=result.deferred_reason,
            timestamp=datetime.utcnow(),
            metadata={
                "evaluation_mode": context.evaluation_mode if context else "standard",
                "confidence": result.metadata.get("confidence"),
                "factors": result.metadata.get("factors"),
            },
        )
        self._trace_writer.append(trace)

    def _compute_hash(self, content: str) -> str:
        """Compute hash for content (never stores raw content)."""
        return hashlib.sha256(content.encode()).hexdigest()

    def _compute_quarantine_time(self, scoring, decision: CACDecision) -> datetime | None:
        """Compute quarantine expiration time if applicable."""
        if decision != CACDecision.QUARANTINED:
            return None
        # Default quarantine: 24 hours
        from datetime import timedelta
        return datetime.utcnow() + timedelta(hours=24)

    def _compute_warning(self, scoring, decision: CACDecision) -> str | None:
        """Compute warning message if applicable."""
        if decision == CACDecision.QUARANTINED:
            return "Memory quarantined pending reviewer disposition"
        if decision == CACDecision.DEFERRED:
            return "Memory decision deferred to human reviewer"
        if scoring.severity == SeverityClass.S2:
            return "Overpersonalization warning"
        return None


# Module-level convenience function
def create_cac_input(
    memory_content: str | None,
    memory_id: str,
    source: MemorySource,
    disputed: bool = False,
    dispute_reason: str | None = None,
    metadata: dict | None = None,
) -> CACInput:
    """Factory function to create a CACInput with hash computation."""
    content_hash = hashlib.sha256(memory_content.encode()).hexdigest() if memory_content else ""
    return CACInput(
        memory_content=memory_content,
        memory_hash=content_hash,
        memory_id=memory_id,
        source=source,
        disputed=disputed,
        dispute_reason=dispute_reason,
        metadata=metadata or {},
    )


def create_cac_context(
    session_id: str,
    evaluation_mode: str = "standard",
    reviewer_id: str | None = None,
) -> CACContext:
    """Factory function to create a CACContext."""
    return CACContext(
        session_id=session_id,
        evaluation_mode=evaluation_mode,
        reviewer_id=reviewer_id,
    )
