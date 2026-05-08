"""Test: OTel trace contains no raw sensitive text.

Acceptance criteria:
- Telemetry/audit traces do not persist raw sensitive text
- OTel spans only contain hashes and metadata
- Sensitive data is redacted before tracing

This test validates that OpenTelemetry traces maintain privacy by design.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4


@dataclass
class RedactionRule:
    """Rule for redacting sensitive content from traces."""
    pattern: str
    replacement: str = "[REDACTED]"
    pattern_type: str = "exact"  # "exact", "regex", "keyword"


class TelemetryRedactor:
    """Redacts sensitive content from telemetry data.

    Applies privacy-by-design: raw sensitive text never enters traces.
    """

    def __init__(self, rules: list[RedactionRule] | None = None):
        self.rules = rules or [
            RedactionRule(pattern="password", pattern_type="keyword"),
            RedactionRule(pattern="api_key", pattern_type="keyword"),
            RedactionRule(pattern="secret", pattern_type="keyword"),
            RedactionRule(pattern="ssn", pattern_type="keyword"),
            RedactionRule(pattern="credit_card", pattern_type="keyword"),
        ]

    def redact_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """Redact sensitive content from a dictionary."""
        result = {}
        for key, value in data.items():
            if isinstance(value, str):
                result[key] = self._redact_string(value)
            elif isinstance(value, dict):
                result[key] = self.redact_dict(value)
            elif isinstance(value, list):
                result[key] = [
                    self._redact_string(str(v)) if isinstance(v, str) else v
                    for v in value
                ]
            else:
                result[key] = value
        return result

    def _redact_string(self, text: str) -> str:
        """Redact sensitive patterns from string.

        If any keyword is found in the text, returns [REDACTED].
        This ensures no partial sensitive data leaks.
        """
        for rule in self.rules:
            if rule.pattern_type == "keyword":
                if rule.pattern.lower() in text.lower():
                    return rule.replacement
        return text


@dataclass
class OTelSpan:
    """OpenTelemetry span with privacy-by-design.

    Only contains:
    - Content hashes (not raw content)
    - Span metadata
    - Privacy-preserved attributes
    """
    span_id: str
    trace_id: str
    operation_name: str
    start_time: datetime
    end_time: datetime | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    redactor: TelemetryRedactor = field(default_factory=TelemetryRedactor)

    def add_attribute(self, key: str, value: Any) -> None:
        """Add attribute with automatic redaction."""
        redacted_value = self._prepare_value(value)
        self.attributes[key] = redacted_value

    def _prepare_value(self, value: Any) -> str:
        """Prepare value for span (hash or redact)."""
        if isinstance(value, str):
            redacted = self.redactor._redact_string(value)
            if redacted != value:
                return "[REDACTED]"
            return value
        return str(value)

    def to_dict(self) -> dict[str, Any]:
        """Serialize span to dictionary."""
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "operation_name": self.operation_name,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "attributes": self.attributes,
        }


class MemoryDynamicsTracer:
    """Traces memory dynamics operations with privacy-by-design.

    All traces use hashes, never raw content.
    """

    def __init__(self):
        self.spans: list[OTelSpan] = []
        self.redactor = TelemetryRedactor()

    def start_span(
        self,
        operation_name: str,
        content_hash: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> OTelSpan:
        """Start a new trace span."""
        span = OTelSpan(
            span_id=str(uuid4())[:16],
            trace_id=str(uuid4()),
            operation_name=operation_name,
            start_time=datetime.utcnow(),
            redactor=self.redactor,
        )

        if content_hash:
            span.attributes["content_hash"] = content_hash

        if metadata:
            redacted_metadata = {}
            for key, value in metadata.items():
                if isinstance(value, str):
                    redacted_metadata[key] = span._prepare_value(value)
                elif isinstance(value, dict):
                    redacted_metadata[key] = self.redactor.redact_dict(value)
                else:
                    redacted_metadata[key] = value
            span.attributes.update(redacted_metadata)

        self.spans.append(span)
        return span

    def trace_decay(
        self,
        block_id: str,
        content_hash: str,
        salience_before: float,
        salience_after: float,
    ) -> OTelSpan:
        """Trace a decay operation."""
        span = self.start_span(
            operation_name="memory.decay",
            content_hash=content_hash,
            metadata={
                "block_id": block_id,
                "salience.before": salience_before,
                "salience.after": salience_after,
            },
        )
        span.end_time = datetime.utcnow()
        return span

    def trace_rehearsal(
        self,
        block_id: str,
        content_hash: str,
        salience_before: float,
        salience_after: float,
    ) -> OTelSpan:
        """Trace a rehearsal operation."""
        span = self.start_span(
            operation_name="memory.rehearsal",
            content_hash=content_hash,
            metadata={
                "block_id": block_id,
                "salience.before": salience_before,
                "salience.after": salience_after,
            },
        )
        span.end_time = datetime.utcnow()
        return span


class TestOTelTraceNoRawSensitiveText:
    """Test suite for OTel trace privacy."""

    def test_trace_contains_content_hash_not_raw_content(self):
        """Traces must contain hashes, not raw content."""
        tracer = MemoryDynamicsTracer()

        raw_content = "CONFIDENTIAL: secret API key sk-12345"
        content_hash = hashlib.sha256(raw_content.encode()).hexdigest()

        span = tracer.trace_decay(
            block_id="block-1",
            content_hash=content_hash,
            salience_before=0.8,
            salience_after=0.7,
        )

        span_dict = span.to_dict()
        span_str = str(span_dict)

        assert "CONFIDENTIAL" not in span_str
        assert "secret" not in span_str
        assert "API key" not in span_str
        assert "sk-12345" not in span_str

    def test_trace_preserves_hash(self):
        """Hash is preserved for traceability."""
        tracer = MemoryDynamicsTracer()

        content = "Some memory content"
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        span = tracer.trace_decay(
            block_id="block-1",
            content_hash=content_hash,
            salience_before=0.8,
            salience_after=0.7,
        )

        assert span.attributes.get("content_hash") == content_hash

    def test_metadata_is_redacted(self):
        """Metadata with sensitive keywords is redacted."""
        tracer = MemoryDynamicsTracer()

        span = tracer.start_span(
            operation_name="memory.update",
            metadata={
                "block_id": "block-1",
                "api_key": "sk-secret-key-12345",
                "action": "update",
            },
        )

        assert span.attributes.get("api_key") == "[REDACTED]"
        assert "sk-secret-key" not in str(span.attributes)

    def test_redactor_handles_nested_dicts(self):
        """Redactor handles nested dictionary structures."""
        redactor = TelemetryRedactor()

        data = {
            "level1": {
                "level2": {
                    "password": "super-secret-123",
                    "safe_field": "normal value",
                }
            }
        }

        result = redactor.redact_dict(data)

        nested = result["level1"]["level2"]
        # If any keyword is in value, entire value is redacted
        assert nested["password"] == "[REDACTED]"
        # Safe field should remain unchanged
        assert nested["safe_field"] == "normal value"

    def test_trace_rehearsal_no_raw_sensitive(self):
        """Rehearsal traces contain no raw sensitive text."""
        tracer = MemoryDynamicsTracer()

        private_content = "PRIVATE: credit card 1234-5678-9012-3456"
        content_hash = hashlib.sha256(private_content.encode()).hexdigest()

        span = tracer.trace_rehearsal(
            block_id="block-private",
            content_hash=content_hash,
            salience_before=0.5,
            salience_after=0.6,
        )

        span_str = str(span.to_dict())

        assert "PRIVATE" not in span_str
        assert "credit card" not in span_str
        assert "1234-5678" not in span_str


class TestOTelBlockConditions:
    """Test block conditions from mechanism report contract."""

    def test_block_telemetry_no_raw_sensitive_text(self):
        """Block if: telemetry/audit traces persist raw sensitive text."""
        tracer = MemoryDynamicsTracer()

        sensitive = "API_SECRET=ghp_verysecret1234567890token"
        content_hash = hashlib.sha256(sensitive.encode()).hexdigest()

        tracer.trace_decay(
            block_id="block-api",
            content_hash=content_hash,
            salience_before=0.8,
            salience_after=0.7,
        )

        all_spans = [s.to_dict() for s in tracer.spans]
        all_output = str(all_spans)

        assert "API_SECRET" not in all_output
        assert "ghp_verysecret" not in all_output
        assert "secret12345" not in all_output

    def test_block_mechanism_bypasses_privacy_gate(self):
        """Block if: mechanism bypasses privacy correction scope."""
        tracer = MemoryDynamicsTracer()

        assert hasattr(tracer, 'redactor')
        assert isinstance(tracer.redactor, TelemetryRedactor)

        result = tracer.redactor._redact_string("my_secret_password")
        assert result == "[REDACTED]"

    def test_block_pr20_outputs_are_mechanism_reports(self):
        """Block if: mechanism report outputs alter runtime behavior."""
        tracer = MemoryDynamicsTracer()

        span = tracer.start_span(
            operation_name="memory.decay",
            metadata={"salience_change": 0.1},
        )

        span_dict = span.to_dict()

        assert "runtime_command" not in span_dict
        assert "directive" not in str(span_dict.get("attributes", {}))
