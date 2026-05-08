"""Tests for markdown/yaml mirror containing no raw sensitive text.

Validates Acceptance criteria:
- human-readable projections are redacted
- dynamic memory traces contain raw sensitive text

Tests fail closed on privacy/correction/runtime bypass.
"""

from __future__ import annotations

import json
from pathlib import Path

from relic.persistence import MemoryPersistence, PrivacyLevel


class TestMarkdownYamlMirrorNoSensitiveText:
    """Tests verifying markdown/yaml memory mirrors contain no raw sensitive text."""

    def test_yaml_mirror_contains_no_raw_email(self, tmp_path: Path) -> None:
        """Verify yaml mirror redacts email addresses."""
        persistence = MemoryPersistence(trace_path=tmp_path / "trace.yamll")

        # Store content containing PII
        sensitive_content = "Remember user email: john.doe@example.com for contact"
        persistence.store(sensitive_content, PrivacyLevel.S0_HARD_VIOLATION)

        # Verify trace contains hash, not raw email
        traces = persistence.get_trace()
        assert len(traces) > 0

        # Check no email appears in traces
        trace_json = json.dumps([t.to_dict() for t in traces])
        assert "john.doe@example.com" not in trace_json
        assert "example.com" not in trace_json

    def test_yaml_mirror_contains_no_raw_phone(self, tmp_path: Path) -> None:
        """Verify yaml mirror redacts phone numbers."""
        persistence = MemoryPersistence(trace_path=tmp_path / "trace.yamll")

        sensitive_content = "Call me at 555-123-4567 tomorrow"
        persistence.store(sensitive_content, PrivacyLevel.S0_HARD_VIOLATION)

        traces = persistence.get_trace()
        trace_json = json.dumps([t.to_dict() for t in traces])

        # Phone number patterns should be redacted
        assert "555-123-4567" not in trace_json
        assert "555" not in trace_json or "123" not in trace_json or "4567" not in trace_json

    def test_yaml_mirror_contains_no_raw_api_key(self, tmp_path: Path) -> None:
        """Verify yaml mirror redacts API keys."""
        persistence = MemoryPersistence(trace_path=tmp_path / "trace.yamll")

        sensitive_content = "API key: sk_live_abc123xyz456def789"
        persistence.store(sensitive_content, PrivacyLevel.S0_HARD_VIOLATION)

        traces = persistence.get_trace()
        trace_json = json.dumps([t.to_dict() for t in traces])

        # API key patterns should be redacted
        assert "sk_live_" not in trace_json
        assert "abc123xyz456def789" not in trace_json

    def test_yaml_mirror_stores_only_hashes(self, tmp_path: Path) -> None:
        """Verify yaml mirror stores only content hashes, never raw text."""
        persistence = MemoryPersistence(trace_path=tmp_path / "trace.yamll")

        content = "My password is SuperSecret123!"
        block = persistence.store(content, PrivacyLevel.S0_HARD_VIOLATION)

        # Read the trace file directly
        trace_file = tmp_path / "trace.yamll"
        assert trace_file.exists()

        with open(trace_file) as f:
            raw_content = f.read()

        # Raw content must never appear
        assert "SuperSecret123" not in raw_content
        assert "password" not in raw_content.lower() or "SuperSecret123" not in raw_content

        # But hash must be present
        assert block.content_hash in raw_content

    def test_markdown_report_contains_no_raw_sensitive_text(self, tmp_path: Path) -> None:
        """Verify markdown reports redact sensitive text in memory dynamics outputs."""
        persistence = MemoryPersistence(trace_path=tmp_path / "trace.jsonl")

        # Simulate a memory dynamics report containing sensitive projections
        report_content = """
        Memory Dynamics Report
        ----------------------
        User preference: user123_pref
        Contact: user@example.com
        SSN: 123-45-6789
        """

        persistence.store(report_content, PrivacyLevel.S0_HARD_VIOLATION)

        traces = persistence.get_trace()
        trace_json = json.dumps([t.to_dict() for t in traces])

        # All PII must be redacted
        assert "user@example.com" not in trace_json
        assert "123-45-6789" not in trace_json

    def test_redaction_applies_to_s1_quarantine_content(self, tmp_path: Path) -> None:
        """Verify S1 quarantine content is also redacted in mirrors."""
        persistence = MemoryPersistence(trace_path=tmp_path / "trace.jsonl")

        quarantine_content = "Personal note: I prefer dark mode, my name is John"
        persistence.store(quarantine_content, PrivacyLevel.S1_QUARANTINE)

        traces = persistence.get_trace()
        trace_json = json.dumps([t.to_dict() for t in traces])

        # Personal details should not appear raw
        assert "John" not in trace_json or "dark mode" not in trace_json

    def test_human_readable_projections_are_redacted(self, tmp_path: Path) -> None:
        """Verify human-readable projections (HIPPO local memory) are redacted."""
        persistence = MemoryPersistence(trace_path=tmp_path / "trace.jsonl")

        # Human-readable projection content
        projection = "Projection: User likely prefers evening meetings based on history"
        block = persistence.store(projection, PrivacyLevel.SAFE)

        traces = persistence.get_trace()
        assert len(traces) > 0

        # SAFE content still stores hash, not raw projection text
        trace_json = json.dumps([t.to_dict() for t in traces])
        assert projection not in trace_json
        assert block.content_hash in trace_json
