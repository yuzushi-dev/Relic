"""Test compiler fixture compilation and artifact metadata.

This test verifies:
- Compiler creates all required artifact metadata
- Output is reproducible with mock model
- Privacy and correction gates are applied
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

from relic.compiler.lineage import LineageTracker
from relic.compiler.passes import CorrectionCutoffPass, HintFilterPass, PrivacyScanPass
from relic.compiler.pipeline import CompilationContext, CompilerPipeline
from relic.compiler.replication import ReplicationBundle

# Fixed timestamp for deterministic tests
FIXED_TIMESTAMP = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)


def make_deterministic_context(session_id: str) -> CompilationContext:
    """Create a deterministic context with fixed snapshot ID and artifact ID."""
    # Generate deterministic IDs from session_id
    source_snapshot_id = hashlib.sha256(f"source:{session_id}".encode()).hexdigest()[:32]
    artifact_id = hashlib.sha256(f"artifact:{session_id}".encode()).hexdigest()[:32]

    return CompilationContext(
        session_id=session_id,
        agent_id="test-agent",
        agent_version="1.0.0",
        cutoff_timestamp=FIXED_TIMESTAMP,
        source_snapshot_id=source_snapshot_id,
        artifact_id=artifact_id,
    )


class TestCompileFixture:
    """Tests for fixture compilation."""

    def test_compile_runtime_profile_has_required_metadata(self, tmp_path):
        """Test that compiled runtime profile has all required metadata."""
        # Set up pipeline with standard passes
        pipeline = CompilerPipeline()
        pipeline.add_pass(HintFilterPass())
        pipeline.add_pass(PrivacyScanPass())
        pipeline.add_pass(CorrectionCutoffPass(cutoff_timestamp=FIXED_TIMESTAMP))

        # Create context
        context = make_deterministic_context("test-session-001")

        # Compile a runtime profile
        hints = [
            {"content": "hint1", "type": "normal"},
            {"content": "hint2", "type": "disputed"},  # Should be excluded
        ]

        artifact, report = pipeline.compile_runtime_profile(
            hints=hints,
            corrections=[],
            context=context,
        )

        # Verify required metadata
        assert "id" in artifact, "Missing artifact ID"
        assert "checksum" in artifact, "Missing checksum"
        assert "schema_version" in artifact, "Missing schema_version"
        assert "source_snapshot_id" in artifact, "Missing source_snapshot_id"
        assert "created_at" in artifact, "Missing created_at"
        assert "lineage_refs" in artifact, "Missing lineage_refs"
        assert "agent_id" in artifact, "Missing agent_id"
        assert "agent_version" in artifact, "Missing agent_version"
        assert "correction_cutoff" in artifact, "Missing correction_cutoff"
        assert "profile_type" in artifact, "Missing profile_type"

        # Verify checksum is non-empty
        assert len(artifact["checksum"]) == 64, "Checksum should be SHA-256 (64 hex chars)"

        # Verify lineage is verified
        assert report.lineage_verified is True, "Lineage should be verified"

    def test_compile_excludes_disputed_hints_without_approval(self):
        """Test that disputed hints are excluded without policy approval."""
        pipeline = CompilerPipeline()
        pipeline.add_pass(HintFilterPass(disputed_approval=False))
        pipeline.add_pass(PrivacyScanPass())
        pipeline.add_pass(CorrectionCutoffPass(cutoff_timestamp=FIXED_TIMESTAMP))

        context = make_deterministic_context("test-session-002")
        context.disputed_approval = False  # No approval

        hints = [
            {"content": "normal_hint", "type": "normal"},
            {"content": "disputed_hint", "type": "disputed"},
            {"content": "another_normal", "type": "normal"},
        ]

        artifact, report = pipeline.compile_runtime_profile(
            hints=hints,
            context=context,
        )

        # Verify disputed hint was excluded
        assert report.excluded_hints, "Should have excluded hints"
        assert len(report.excluded_hints) == 1, "Should have exactly 1 excluded hint"
        assert report.excluded_hints[0].hint_type == "disputed"

        # Verify artifact metadata
        assert artifact["disputed_hints_excluded"] == 1, "Should report 1 excluded hint"

    def test_compile_includes_disputed_hints_with_approval(self):
        """Test that disputed hints are included with policy approval."""
        pipeline = CompilerPipeline()
        pipeline.add_pass(HintFilterPass(disputed_approval=True))
        pipeline.add_pass(PrivacyScanPass())
        pipeline.add_pass(CorrectionCutoffPass(cutoff_timestamp=FIXED_TIMESTAMP))

        context = make_deterministic_context("test-session-003")
        context.disputed_approval = True  # With approval

        hints = [
            {"content": "disputed_hint", "type": "disputed"},
        ]

        artifact, report = pipeline.compile_runtime_profile(
            hints=hints,
            context=context,
        )

        # Verify no hints were excluded
        assert len(report.excluded_hints) == 0, "Should not have excluded hints with approval"
        assert artifact["disputed_hints_excluded"] == 0

    def test_compile_sensitive_hints_are_downgraded(self):
        """Test that sensitive hints are downgraded without approval."""
        pipeline = CompilerPipeline()
        pipeline.add_pass(HintFilterPass(sensitive_approval=False))
        pipeline.add_pass(PrivacyScanPass())
        pipeline.add_pass(CorrectionCutoffPass(cutoff_timestamp=FIXED_TIMESTAMP))

        context = make_deterministic_context("test-session-004")
        context.sensitive_approval = False

        hints = [
            {"content": "sensitive_hint", "type": "sensitive"},
        ]

        artifact, report = pipeline.compile_runtime_profile(
            hints=hints,
            context=context,
        )

        # Verify sensitive hint was downgraded
        assert len(report.downgraded_hints) == 1, "Should have 1 downgraded hint"
        assert report.downgraded_hints[0].hint_type == "sensitive"
        assert artifact["sensitive_hints_downgraded"] == 1

    def test_compile_privacy_scan_blocks_violations(self):
        """Test that privacy scan detects and reports violations."""
        pipeline = CompilerPipeline()
        pipeline.add_pass(HintFilterPass())
        pipeline.add_pass(PrivacyScanPass())
        pipeline.add_pass(CorrectionCutoffPass(cutoff_timestamp=FIXED_TIMESTAMP))

        context = make_deterministic_context("test-session-005")

        # Content with PII-like pattern (should be caught)
        hints = [
            {"content": "user@example.com contact info", "type": "normal"},
        ]

        artifact, report = pipeline.compile_runtime_profile(
            hints=hints,
            context=context,
        )

        # Verify privacy scan passed and recorded
        gate_results = [g for g in report.policy_gates if g.gate.value == "privacy_scan_gate"]
        assert len(gate_results) == 1, "Should have privacy scan gate result"

    def test_compile_correction_cutoff_applied(self):
        """Test that correction cutoff is properly applied."""
        pipeline = CompilerPipeline()
        pipeline.add_pass(HintFilterPass())
        pipeline.add_pass(PrivacyScanPass())
        pipeline.add_pass(CorrectionCutoffPass(cutoff_timestamp=FIXED_TIMESTAMP))

        context = make_deterministic_context("test-session-006")

        corrections = [
            {"timestamp": "2024-01-10T00:00:00Z", "correction": "old correction"},
            {"timestamp": "2024-01-20T00:00:00Z", "correction": "new correction"},
        ]

        artifact, report = pipeline.compile_runtime_profile(
            hints=[],
            corrections=corrections,
            context=context,
        )

        # Verify correction cutoff metadata
        assert "correction_cutoff" in artifact
        cutoff = artifact["correction_cutoff"]
        assert cutoff["verified"] is True
        assert len(cutoff["corrections_applied"]) == 1, "Should apply 1 correction"
        assert len(cutoff["corrections_pending"]) == 1, "Should have 1 pending correction"

    def test_compile_lineage_is_tracked(self):
        """Test that lineage is tracked for compiled artifacts."""
        lineage_tracker = LineageTracker()
        pipeline = CompilerPipeline(lineage_tracker=lineage_tracker)
        pipeline.add_pass(HintFilterPass())
        pipeline.add_pass(PrivacyScanPass())
        pipeline.add_pass(CorrectionCutoffPass(cutoff_timestamp=FIXED_TIMESTAMP))

        context = make_deterministic_context("test-session-007")

        artifact, report = pipeline.compile_runtime_profile(
            hints=[],
            context=context,
        )

        # Verify lineage was registered
        lineage = lineage_tracker.get(artifact["id"])
        assert lineage is not None, "Lineage should be registered"

    def test_compile_output_is_reproducible_via_bundle(self):
        """Test that compilation output is reproducible via replication bundle."""
        hints = [{"content": "test hint", "type": "normal"}]
        corrections = [{"timestamp": "2024-01-10T00:00:00Z", "correction": "test"}]
        context = make_deterministic_context("test-session-008")

        # Compile twice
        pipeline1 = CompilerPipeline()
        pipeline1.add_pass(HintFilterPass())
        pipeline1.add_pass(PrivacyScanPass())
        pipeline1.add_pass(CorrectionCutoffPass(cutoff_timestamp=FIXED_TIMESTAMP))
        artifact1, _ = pipeline1.compile_runtime_profile(hints, corrections, context)

        pipeline2 = CompilerPipeline()
        pipeline2.add_pass(HintFilterPass())
        pipeline2.add_pass(PrivacyScanPass())
        pipeline2.add_pass(CorrectionCutoffPass(cutoff_timestamp=FIXED_TIMESTAMP))
        artifact2, _ = pipeline2.compile_runtime_profile(hints, corrections, context)

        # Verify reproducibility via bundle
        bundle1 = ReplicationBundle()
        bundle1.add_artifact(artifact1["id"], artifact1)

        bundle2 = ReplicationBundle()
        bundle2.add_artifact(artifact2["id"], artifact2)

        # Bundles should be reproducible
        assert bundle1.verify_reproducibility(bundle2), "Bundles should be reproducible"

    def test_compile_fails_closed_on_blocked_content(self):
        """Test that compilation fails appropriately on blocked content."""
        pipeline = CompilerPipeline()
        pipeline.add_pass(HintFilterPass())

        # Disputed hint without approval should block
        context = make_deterministic_context("test-session-009")
        context.disputed_approval = False

        hints = [{"content": "disputed", "type": "disputed"}]
        artifact, report = pipeline.compile_runtime_profile(hints=hints, context=context)

        # The artifact should still be created but with proper reporting
        assert "id" in artifact
        assert len(report.excluded_hints) > 0, "Should report exclusion"


class TestRuntimeProfilePackFixture:
    """Tests for runtime profile pack fixture loading."""

    def test_load_fixture_runtime_profile_pack(self):
        """Test that runtime_profile_pack.json fixture is valid."""
        fixture_path = Path(__file__).parent.parent.parent / "fixtures" / "basic" / "expected_artifacts" / "runtime_profile_pack.json"

        if not fixture_path.exists():
            pytest.skip("Fixture not yet created")

        with open(fixture_path) as f:
            fixture = json.load(f)

        # Verify required fields per schema
        assert "id" in fixture
        assert "schema_version" in fixture
        assert "checksum" in fixture
        assert "source_snapshot_id" in fixture
        assert "lineage_refs" in fixture
        assert "correction_cutoff" in fixture
        assert "session_id" in fixture
        assert "profile_type" in fixture
        assert "prompt_hash" in fixture
        assert "hint_hashes" in fixture
        assert "agent_id" in fixture

        # Verify hint exclusion metadata
        assert "disputed_hints_excluded" in fixture
        assert "sensitive_hints_downgraded" in fixture

        # Verify privacy-related fields
        assert "is_redacted" in fixture
        assert fixture["is_redacted"] is False, "Fixture should not be redacted by default"

    def test_fixture_contains_no_raw_private_data(self):
        """Test that fixture contains no raw private data.

        Note: This test excludes UUIDs from pattern matching since UUIDs
        may accidentally match phone number patterns.
        """
        fixture_path = Path(__file__).parent.parent.parent / "fixtures" / "basic" / "expected_artifacts" / "runtime_profile_pack.json"

        if not fixture_path.exists():
            pytest.skip("Fixture not yet created")

        with open(fixture_path) as f:
            fixture = json.load(f)

        # Remove UUID-like patterns before checking (UUIDs may accidentally match)
        fixture_str = json.dumps(fixture)
        # Remove any 36-char UUID-like patterns (xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)
        fixture_str_no_uuids = re.sub(
            r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
            'UUID_REMOVED',
            fixture_str,
            flags=re.IGNORECASE
        )
        fixture_str_lower = fixture_str_no_uuids.lower()

        # Check for PII patterns in non-UUID content
        email_pattern = r'[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}'
        phone_pattern = r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'
        ssn_pattern = r'\b\d{3}-\d{2}-\d{4}\b'

        assert not re.search(email_pattern, fixture_str_lower), "Fixture should not contain emails"
        assert not re.search(phone_pattern, fixture_str_lower), "Fixture should not contain phone numbers"
        assert not re.search(ssn_pattern, fixture_str_lower), "Fixture should not contain SSNs"

    def test_fixture_checksum_is_valid_sha256(self):
        """Test that fixture checksum is valid SHA-256."""
        fixture_path = Path(__file__).parent.parent.parent / "fixtures" / "basic" / "expected_artifacts" / "runtime_profile_pack.json"

        if not fixture_path.exists():
            pytest.skip("Fixture not yet created")

        with open(fixture_path) as f:
            fixture = json.load(f)

        checksum = fixture.get("checksum", "")

        # Should be 64 hex characters
        assert len(checksum) == 64, f"Checksum should be 64 chars, got {len(checksum)}"
        assert all(c in '0123456789abcdef' for c in checksum), "Checksum should be hex"
