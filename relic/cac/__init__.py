"""CAC (Correction/Admission/Compliance) gate implementation.

This package provides the memory gate infrastructure:
- controller: Main CAC controller
- types: Type definitions (SeverityClass, CACDecision, etc.)
- scoring: Severity scoring and classification
- trace: Audit trace writer for cac_trace.jsonl
- render: Output rendering for decisions
"""

from relic.cac.controller import CACController, create_cac_context, create_cac_input
from relic.cac.render import CACRenderer, RenderResult
from relic.cac.scoring import CACScorer, ScoringResult
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

__all__ = [
    # Controller
    "CACController",
    "create_cac_input",
    "create_cac_context",
    # Types
    "CACDecision",
    "CACDecisionResult",
    "CACInput",
    "CACContext",
    "CACTrace",
    "MemorySource",
    "SeverityClass",
    # Scoring
    "CACScorer",
    "ScoringResult",
    # Trace
    "CACTraceWriter",
    # Render
    "CACRenderer",
    "RenderResult",
]
