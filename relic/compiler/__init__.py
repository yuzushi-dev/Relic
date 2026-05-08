"""Relic E2E Compiler module.

This module provides compilation of runtime artifacts with zero-knowledge
guarantees. The compiler spine orchestrates:
- Artifact metadata generation
- Lineage and checksum tracking
- Privacy/correction gate reporting
- Reproducible output generation
"""

from relic.compiler.lineage import (
    ArtifactLineage,
    LineageTracker,
)
from relic.compiler.passes import (
    CompilePass,
    CorrectionCutoffPass,
    HintFilterPass,
    PrivacyScanPass,
)
from relic.compiler.pipeline import CompilerPipeline
from relic.compiler.replication import ReplicationBundle
from relic.compiler.report import CompilerReport, ExcludedHint

__all__ = [
    "ArtifactLineage",
    "CompilerPipeline",
    "CompilerReport",
    "CompilePass",
    "CorrectionCutoffPass",
    "ExcludedHint",
    "HintFilterPass",
    "LineageTracker",
    "PrivacyScanPass",
    "ReplicationBundle",
]
