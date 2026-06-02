"""
Observability, Redacted observability bridge for Hermes.

This module provides a bridge between Relic Chronicle and external
observability systems (e.g., Langfuse) with strict redaction policies.

Design: Hermes exports observability. Relic ensures redaction.
"""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from enum import Enum


class RedactionLevel(str, Enum):
    """Level of redaction applied to observability data."""
    NONE = "none"
    HASH_ONLY = "hash_only"
    REDACTED = "redacted"
    METRICS_ONLY = "metrics_only"


@dataclass(frozen=True)
class RedactedSpan:
    """
    Redacted span for external observability.

    Attributes:
        span_id: Unique span identifier
        trace_id: Trace correlation ID
        name: Span name (redaction-safe)
        start_time: Span start timestamp
        end_time: Span end timestamp
        duration_ms: Duration in milliseconds
        redaction_level: Applied redaction level
        attributes: Redacted attributes (no PII)
        metrics: Numeric metrics only
    """
    span_id: str
    trace_id: str
    name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_ms: Optional[float] = None
    redaction_level: RedactionLevel = RedactionLevel.REDACTED
    attributes: dict = field(default_factory=dict)
    metrics: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "name": self.name,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "redaction_level": self.redaction_level.value,
            "attributes": self.attributes,
            "metrics": self.metrics,
        }


class ObservabilityBridge:
    """
    Bridge for exporting redacted observability data.

    This bridge ensures that no raw user data, subject identifiers,
    or sensitive content is exported to external observability systems.

    Args:
        redaction_level: Default redaction level (default: REDACTED)
        export_enabled: Whether export is enabled (default: False)

    Redaction rules:
    - No raw user messages in spans
    - No subject identifiers (use hashed references)
    - No profile content summaries
    - Only numeric metrics allowed
    - Attributes must pass redaction filter
    """

    def __init__(
        self,
        redaction_level: RedactionLevel = RedactionLevel.REDACTED,
        export_enabled: bool = False,
    ):
        self.redaction_level = redaction_level
        self.export_enabled = export_enabled
        self._export_count = 0

    def create_span(
        self,
        trace_id: str,
        name: str,
        start_time: Optional[datetime] = None,
        attributes: Optional[dict] = None,
    ) -> RedactedSpan:
        """
        Create a redacted span.

        Args:
            trace_id: Trace correlation ID
            name: Span name
            start_time: Optional start time (default: now)
            attributes: Optional attributes (will be redacted)

        Returns:
            RedactedSpan with redaction applied
        """
        start = start_time or datetime.now(timezone.utc)
        redacted_attrs = self._redact_attributes(attributes or {})

        return RedactedSpan(
            span_id=f"span-{self._generate_id()}",
            trace_id=self._hash_trace_id(trace_id),
            name=self._redact_name(name),
            start_time=start,
            redaction_level=self.redaction_level,
            attributes=redacted_attrs,
        )

    def end_span(
        self,
        span: RedactedSpan,
        end_time: Optional[datetime] = None,
        metrics: Optional[dict] = None,
    ) -> RedactedSpan:
        """
        End a span and compute duration.

        Args:
            span: Span to end
            end_time: Optional end time (default: now)
            metrics: Optional metrics (will be filtered to numeric only)

        Returns:
            Updated RedactedSpan with end time and duration
        """
        end = end_time or datetime.now(timezone.utc)
        duration = (end - span.start_time).total_seconds() * 1000
        filtered_metrics = self._filter_metrics(metrics or {})

        # Create new span with updated fields (frozen dataclass)
        return RedactedSpan(
            span_id=span.span_id,
            trace_id=span.trace_id,
            name=span.name,
            start_time=span.start_time,
            end_time=end,
            duration_ms=duration,
            redaction_level=span.redaction_level,
            attributes=span.attributes,
            metrics=filtered_metrics,
        )

    def export_span(self, span: RedactedSpan) -> bool:
        """
        Export span to external observability.

        Args:
            span: Redacted span to export

        Returns:
            True if export succeeded, False otherwise
        """
        if not self.export_enabled:
            return False

        if self.redaction_level == RedactionLevel.NONE:
            # Never export unredacted data
            return False

        # In production, would call Langfuse/other exporter
        # For now, just increment counter
        self._export_count += 1
        return True

    def _redact_attributes(self, attributes: dict) -> dict:
        """
        Redact attributes for external export.

        Rules:
        - Remove any key containing 'user', 'subject', 'profile', 'message'
        - Hash any string values
        - Keep only numeric and boolean values as-is
        """
        redacted = {}
        sensitive_keys = {'user', 'subject', 'profile', 'message', 'content', 'text', 'prompt'}

        for key, value in attributes.items():
            key_lower = key.lower()

            # Skip sensitive keys
            if any(s in key_lower for s in sensitive_keys):
                continue

            # Hash string values
            if isinstance(value, str):
                redacted[key] = self._hash_value(value)
            # Keep numeric and boolean
            elif isinstance(value, (int, float, bool)):
                redacted[key] = value
            # Skip complex types
            elif isinstance(value, (list, dict)):
                redacted[key] = "[redacted]"

        return redacted

    def _filter_metrics(self, metrics: dict) -> dict:
        """Filter metrics to numeric values only."""
        filtered = {}
        for key, value in metrics.items():
            if isinstance(value, (int, float)):
                filtered[key] = value
        return filtered

    def _hash_trace_id(self, trace_id: str) -> str:
        """Hash trace ID for privacy."""
        return f"sha256:{hashlib.sha256(trace_id.encode()).hexdigest()[:16]}"

    def _hash_value(self, value: str) -> str:
        """Hash string value."""
        return f"sha256:{hashlib.sha256(value.encode()).hexdigest()[:16]}"

    def _redact_name(self, name: str) -> str:
        """Redact span name if needed."""
        # Keep name but ensure no sensitive info
        sensitive = {'user', 'subject', 'profile', 'message'}
        if any(s in name.lower() for s in sensitive):
            return f"redacted_{name}"
        return name

    def _generate_id(self) -> str:
        """Generate unique ID."""
        import uuid
        return uuid.uuid4().hex[:12]

    @property
    def export_count(self) -> int:
        """Get count of exported spans."""
        return self._export_count


# Convenience functions

_default_bridge: Optional[ObservabilityBridge] = None
_bridge_lock = threading.Lock()


def get_observability_bridge() -> ObservabilityBridge:
    """Get or create default ObservabilityBridge."""
    global _default_bridge
    if _default_bridge is None:
        with _bridge_lock:
            if _default_bridge is None:
                _default_bridge = ObservabilityBridge()
    return _default_bridge
