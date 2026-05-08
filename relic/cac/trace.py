"""CAC trace writer - Audit logging for memory decisions.

This module handles writing CAC decisions to cac_trace.jsonl.
NEVER writes raw session text to traces.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import TextIO

from relic.cac.types import CACTrace

try:
    import structlog
    logger = structlog.get_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)


class CACTraceWriter:
    """Writes CAC decisions to cac_trace.jsonl for audit.

    Guarantees:
    - Never writes raw session text
    - Always writes to the trace file
    - Provides read-back capability for verification
    """

    def __init__(self, trace_path: Path | str | None = None):
        self._trace_path = Path(trace_path) if trace_path else Path("cac_trace.jsonl")
        self._trace_path.parent.mkdir(parents=True, exist_ok=True)
        self._file_handle: TextIO | None = None

    def append(self, trace: CACTrace) -> None:
        """Append a CAC trace entry to the trace file.

        This is called for every CAC decision to maintain audit trail.
        """
        try:
            with open(self._trace_path, "a") as f:
                f.write(json.dumps(trace.to_dict()) + "\n")
            logger.debug("cac_trace_written",
                        trace_id=trace.trace_id,
                        decision=trace.decision,
                        severity=trace.severity)
        except Exception as e:
            logger.error("cac_trace_write_failed", error=str(e))
            raise

    def append_batch(self, traces: list[CACTrace]) -> None:
        """Append multiple traces efficiently."""
        try:
            with open(self._trace_path, "a") as f:
                for trace in traces:
                    f.write(json.dumps(trace.to_dict()) + "\n")
            logger.debug("cac_trace_batch_written", count=len(traces))
        except Exception as e:
            logger.error("cac_trace_batch_write_failed", error=str(e))
            raise

    def read_all(self) -> list[CACTrace]:
        """Read all traces from the trace file."""
        traces = []
        if not self._trace_path.exists():
            return traces

        with open(self._trace_path) as f:
            for line in f:
                if line.strip():
                    traces.append(CACTrace.from_dict(json.loads(line)))
        return traces

    def clear(self) -> None:
        """Clear the trace file (for testing)."""
        if self._trace_path.exists():
            self._trace_path.unlink()
        self._file_handle = None

    def exists(self) -> bool:
        """Check if trace file exists."""
        return self._trace_path.exists()

    @property
    def trace_path(self) -> Path:
        """Return the trace file path."""
        return self._trace_path

    def get_traces_for_memory(self, memory_id: str) -> list[CACTrace]:
        """Get all traces for a specific memory ID."""
        return [t for t in self.read_all() if t.memory_id == memory_id]


def create_trace_from_result(
    trace_id: str,
    memory_id: str,
    memory_hash: str,
    source: str,
    decision: str,
    severity: str,
    disputed: bool,
    skip_reason: str | None = None,
    deferred_reason: str | None = None,
    metadata: dict | None = None,
) -> CACTrace:
    """Factory function to create a CACTrace from decision result parameters."""
    return CACTrace(
        trace_id=trace_id,
        memory_id=memory_id,
        memory_hash=memory_hash,
        source=source,
        decision=decision,
        severity=severity,
        disputed=disputed,
        skip_reason=skip_reason,
        deferred_reason=deferred_reason,
        timestamp=datetime.utcnow(),
        metadata=metadata or {},
    )
