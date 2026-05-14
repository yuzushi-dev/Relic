"""CAC to PromptContextPack adapter.

This adapter converts CAC decisions into PromptContextPack memory
candidates and blocked items. CAC becomes the ONLY path by which
memory candidates are admitted into injected runtime context.

Key guarantees:
- S0/S1 memories are NEVER admitted as candidates
- Disputed hints are NEVER admitted
- All admitted candidates go through CAC scoring
- Blocked items are tracked for audit purposes
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from relic.cac.types import (
    CACDecision,
    CACDecisionResult,
    CACInput,
    CACTrace,
    MemorySource,
    SeverityClass,
)
from relic.context_pack.types import (
    MemoryCandidate as PCP_MEMORY_CANDIDATE,
    BlockedItem as PCP_BLOCKED_ITEM,
    PromptContextPack,
)

try:
    import structlog
    logger = structlog.get_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)


@dataclass
class CACContextPackAdapterResult:
    """Result of CAC context pack adaptation.
    
    Contains all admitted memory candidates and blocked items.
    """
    candidates: list[PCP_MEMORY_CANDIDATE] = field(default_factory=list)
    blocked: list[PCP_BLOCKED_ITEM] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class CACContextPackAdapter:
    """Adapter converting CAC decisions to PromptContextPack format.
    
    This adapter is the ONLY path for memory candidates to enter
    runtime context. It enforces:
    - S0: Hard block, never admitted
    - S1: Quarantine, never admitted (zero runtime influence)
    - Disputed: Always blocked, never admitted
    - S2: Admitted with warning
    - NONE: Admitted based on render mode
    """

    def adapt(
        self,
        inp: CACInput,
        result: CACDecisionResult,
    ) -> CACContextPackAdapterResult:
        """Adapt a single CAC decision to context pack format.
        
        Args:
            inp: Original CAC input
            result: CAC decision result
            
        Returns:
            CACContextPackAdapterResult with candidates and blocked items
        """
        # Check for disputed - ALWAYS blocked
        if inp.disputed:
            blocked_item = self._create_blocked_from_disputed(inp, result)
            return CACContextPackAdapterResult(
                candidates=[],
                blocked=[blocked_item],
                metadata={"blocked_count": 1, "admitted_count": 0},
            )

        # Check severity - S0 and S1 are never admitted
        if result.severity in (SeverityClass.S0, SeverityClass.S1):
            blocked_item = self._create_blocked_from_severity(inp, result)
            return CACContextPackAdapterResult(
                candidates=[],
                blocked=[blocked_item],
                metadata={"blocked_count": 1, "admitted_count": 0},
            )

        # Check decision - QUARANTINED never admitted
        if result.decision == CACDecision.QUARANTINED:
            blocked_item = self._create_blocked_from_quarantine(inp, result)
            return CACContextPackAdapterResult(
                candidates=[],
                blocked=[blocked_item],
                metadata={"blocked_count": 1, "admitted_count": 0},
            )

        # Check decision - BLOCKED never admitted
        if result.decision == CACDecision.BLOCKED:
            blocked_item = self._create_blocked_from_decision(inp, result)
            return CACContextPackAdapterResult(
                candidates=[],
                blocked=[blocked_item],
                metadata={"blocked_count": 1, "admitted_count": 0},
            )

        # Check decision - DEFERRED never admitted
        if result.decision == CACDecision.DEFERRED:
            blocked_item = self._create_blocked_from_deferred(inp, result)
            return CACContextPackAdapterResult(
                candidates=[],
                blocked=[blocked_item],
                metadata={"blocked_count": 1, "admitted_count": 0},
            )

        # Check decision - NONE means no content to admit
        if result.decision == CACDecision.NONE or not inp.memory_content:
            return CACContextPackAdapterResult(
                candidates=[],
                blocked=[],
                metadata={"blocked_count": 0, "admitted_count": 0},
            )

        # Admitted decisions
        candidate = self._create_candidate(inp, result)
        return CACContextPackAdapterResult(
            candidates=[candidate],
            blocked=[],
            metadata={"blocked_count": 0, "admitted_count": 1},
        )

    def adapt_batch(
        self,
        inputs: list[tuple[CACInput, CACDecisionResult]],
    ) -> CACContextPackAdapterResult:
        """Adapt multiple CAC decisions to context pack format.
        
        Args:
            inputs: List of (CACInput, CACDecisionResult) tuples
            
        Returns:
            Aggregated CACContextPackAdapterResult
        """
        all_candidates: list[PCP_MEMORY_CANDIDATE] = []
        all_blocked: list[PCP_BLOCKED_ITEM] = []
        admitted_count = 0
        blocked_count = 0

        for inp, result in inputs:
            adapt_result = self.adapt(inp, result)
            all_candidates.extend(adapt_result.candidates)
            all_blocked.extend(adapt_result.blocked)
            admitted_count += len(adapt_result.candidates)
            blocked_count += len(adapt_result.blocked)

        return CACContextPackAdapterResult(
            candidates=all_candidates,
            blocked=all_blocked,
            metadata={
                "blocked_count": blocked_count,
                "admitted_count": admitted_count,
                "total_processed": len(inputs),
            },
        )

    def adapt_from_trace(
        self,
        trace: CACTrace,
    ) -> CACContextPackAdapterResult:
        """Adapt from a CAC trace (for replay/audit purposes).
        
        Note: This reconstructs the decision from trace data.
        Original content is NOT available in traces.
        """
        # Reconstruct what we can from the trace
        # Note: memory_content is NOT in traces (privacy guarantee)
        source = trace.source if isinstance(trace.source, str) else str(trace.source)
        decision = trace.decision if isinstance(trace.decision, str) else str(trace.decision)
        severity = trace.severity if isinstance(trace.severity, str) else str(trace.severity)

        # If it was blocked or quarantined, it's blocked
        if decision in (CACDecision.BLOCKED.value, CACDecision.QUARANTINED.value):
            return CACContextPackAdapterResult(
                candidates=[],
                blocked=[
                    PCP_BLOCKED_ITEM(
                        item_id=trace.memory_id,
                        reason=f"trace_replay:{decision}",
                        scope=[],
                        metadata={
                            "memory_hash": trace.memory_hash,
                            "source": source,
                            "severity": severity,
                            "skip_reason": trace.skip_reason,
                            "disputed": trace.disputed,
                        },
                    )
                ],
                metadata={"from_trace": True, "blocked_count": 1},
            )

        # If it was admitted, we can't reconstruct content but note it
        return CACContextPackAdapterResult(
            candidates=[],
            blocked=[],
            metadata={
                "from_trace": True,
                "note": "original_content_not_available_in_trace",
                "decision": decision,
                "severity": severity,
            },
        )

    def _create_candidate(
        self,
        inp: CACInput,
        result: CACDecisionResult,
    ) -> PCP_MEMORY_CANDIDATE:
        """Create a memory candidate from admitted decision."""
        source = inp.source.value if isinstance(inp.source, MemorySource) else str(inp.source)
        decision = result.decision.value if isinstance(result.decision, CACDecision) else str(result.decision)
        severity = result.severity.value if isinstance(result.severity, SeverityClass) else str(result.severity)

        # Determine memory type from source
        memory_type = self._get_memory_type(source, result)

        return PCP_MEMORY_CANDIDATE(
            candidate_id=inp.memory_id,
            memory_type=memory_type,
            summary=inp.memory_content or "",
            relevance_score=result.metadata.get("confidence", 0.5),
            source=source,
            timestamp=datetime.now(timezone.utc),
            metadata={
                "decision": decision,
                "severity": severity,
                "factors": result.metadata.get("factors"),
            },
        )

    def _create_blocked_from_disputed(
        self,
        inp: CACInput,
        result: CACDecisionResult,
    ) -> PCP_BLOCKED_ITEM:
        """Create blocked item for disputed memory."""
        source = inp.source.value if isinstance(inp.source, MemorySource) else str(inp.source)
        severity = result.severity.value if isinstance(result.severity, SeverityClass) else str(result.severity)

        return PCP_BLOCKED_ITEM(
            item_id=inp.memory_id,
            reason=f"disputed:{inp.dispute_reason or 'disputed'}",
            scope=[],
            metadata={
                "memory_hash": result.memory_hash,
                "source": source,
                "severity": severity,
                "skip_reason": result.skip_reason,
            },
        )

    def _create_blocked_from_severity(
        self,
        inp: CACInput,
        result: CACDecisionResult,
    ) -> PCP_BLOCKED_ITEM:
        """Create blocked item for S0/S1 severity."""
        source = inp.source.value if isinstance(inp.source, MemorySource) else str(inp.source)
        severity = result.severity.value if isinstance(result.severity, SeverityClass) else str(result.severity)

        return PCP_BLOCKED_ITEM(
            item_id=inp.memory_id,
            reason=f"severity_{severity}:{result.skip_reason or 'hard_block'}",
            scope=[],
            metadata={
                "memory_hash": result.memory_hash,
                "source": source,
                "skip_reason": result.skip_reason,
            },
        )

    def _create_blocked_from_quarantine(
        self,
        inp: CACInput,
        result: CACDecisionResult,
    ) -> PCP_BLOCKED_ITEM:
        """Create blocked item for quarantined decision."""
        source = inp.source.value if isinstance(inp.source, MemorySource) else str(inp.source)

        return PCP_BLOCKED_ITEM(
            item_id=inp.memory_id,
            reason="quarantined",
            scope=[],
            metadata={
                "memory_hash": result.memory_hash,
                "source": source,
                "quarantine_until": result.quarantine_until.isoformat() if result.quarantine_until else None,
                "skip_reason": result.skip_reason,
            },
        )

    def _create_blocked_from_decision(
        self,
        inp: CACInput,
        result: CACDecisionResult,
    ) -> PCP_BLOCKED_ITEM:
        """Create blocked item for BLOCKED decision."""
        source = inp.source.value if isinstance(inp.source, MemorySource) else str(inp.source)

        return PCP_BLOCKED_ITEM(
            item_id=inp.memory_id,
            reason=f"blocked:{result.skip_reason or 'policy_violation'}",
            scope=[],
            metadata={
                "memory_hash": result.memory_hash,
                "source": source,
                "skip_reason": result.skip_reason,
            },
        )

    def _create_blocked_from_deferred(
        self,
        inp: CACInput,
        result: CACDecisionResult,
    ) -> PCP_BLOCKED_ITEM:
        """Create blocked item for DEFERRED decision."""
        source = inp.source.value if isinstance(inp.source, MemorySource) else str(inp.source)

        return PCP_BLOCKED_ITEM(
            item_id=inp.memory_id,
            reason=f"deferred:{result.deferred_reason or 'pending_review'}",
            scope=[],
            metadata={
                "memory_hash": result.memory_hash,
                "source": source,
                "skip_reason": result.skip_reason,
            },
        )

    def _get_memory_type(self, source: str, result: CACDecisionResult) -> str:
        """Get memory type from source and decision."""
        source_to_type = {
            MemorySource.USER_CORRECTION.value: "user_correction",
            MemorySource.PROVIDER_MEMORY.value: "provider_memory",
            MemorySource.INFERENCE.value: "inference",
            MemorySource.EXTERNAL.value: "external",
            MemorySource.UNKNOWN.value: "unknown",
        }
        return source_to_type.get(source, "general")
