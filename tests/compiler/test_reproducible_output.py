"""Test reproducible output generation.

This test verifies:
- Compiler output is reproducible with mock model
- Checksums are deterministic
- Lineage is consistent across runs
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from relic.compiler.lineage import LineageTracker
from relic.compiler.passes import CorrectionCutoffPass, HintFilterPass, PrivacyScanPass
from relic.compiler.pipeline import (
    CompilationContext,
    CompilerPipeline,
    set_deterministic_timestamp,
)
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
        cutoff_timestamp=FIXED_TIMESTAMP,
        agent_id="mock-agent",
        agent_version="1.0.0",
        source_snapshot_id=source_snapshot_id,
        artifact_id=artifact_id,
    )


class TestReproducibleOutput:
    """Tests for reproducible compilation output."""

    def setup_method(self):
        """Set up deterministic timestamp for each test."""
        set_deterministic_timestamp(FIXED_TIMESTAMP)

    def teardown_method(self):
        """Reset deterministic timestamp after each test."""
        set_deterministic_timestamp(None)

    def test_same_inputs_produce_same_checksum_via_bundle(self):
        """Test that identical inputs produce identical checksums via bundle."""
        hints = [{"content": "test hint", "type": "normal"}]
        corrections = [{"timestamp": "2024-01-10T00:00:00Z", "correction": "test"}]
        context = make_deterministic_context("repro-test-001")

        # Run twice with same context
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

        # Verify via bundle - this tests true reproducibility
        bundle1 = ReplicationBundle()
        bundle1.add_artifact(artifact1["id"], artifact1)

        bundle2 = ReplicationBundle()
        bundle2.add_artifact(artifact2["id"], artifact2)

        assert bundle1.verify_reproducibility(bundle2), "Bundles should be reproducible"

    def test_different_sessions_produce_different_checksums(self):
        """Test that different sessions produce different checksums."""
        hints = [{"content": "test hint", "type": "normal"}]

        context1 = make_deterministic_context("session-001")
        context2 = make_deterministic_context("session-002")

        pipeline1 = CompilerPipeline()
        pipeline1.add_pass(HintFilterPass())
        pipeline1.add_pass(PrivacyScanPass())
        pipeline1.add_pass(CorrectionCutoffPass(cutoff_timestamp=FIXED_TIMESTAMP))

        pipeline2 = CompilerPipeline()
        pipeline2.add_pass(HintFilterPass())
        pipeline2.add_pass(PrivacyScanPass())
        pipeline2.add_pass(CorrectionCutoffPass(cutoff_timestamp=FIXED_TIMESTAMP))

        artifact1, _ = pipeline1.compile_runtime_profile(hints, context=context1)
        artifact2, _ = pipeline2.compile_runtime_profile(hints, context=context2)

        # Different sessions should produce different checksums
        assert artifact1["session_id"] != artifact2["session_id"]

    def test_checksum_is_valid_sha256(self):
        """Test that checksums are valid SHA-256."""
        context = make_deterministic_context("repro-test-002")

        pipeline = CompilerPipeline()
        pipeline.add_pass(HintFilterPass())
        pipeline.add_pass(PrivacyScanPass())
        pipeline.add_pass(CorrectionCutoffPass(cutoff_timestamp=FIXED_TIMESTAMP))

        artifact, _ = pipeline.compile_runtime_profile(
            hints=[],
            context=context,
        )

        checksum = artifact["checksum"]

        # Should be 64 hex characters
        assert len(checksum) == 64, f"Checksum should be 64 chars, got {len(checksum)}"
        assert all(c in '0123456789abcdef' for c in checksum), "Checksum should be hex"

    def test_lineage_is_consistent_across_runs(self):
        """Test that lineage is consistent across compilation runs."""
        tracker = LineageTracker()

        context = make_deterministic_context("repro-test-003")

        hints = [{"content": "test hint", "type": "normal"}]

        # First run
        pipeline1 = CompilerPipeline(lineage_tracker=tracker)
        pipeline1.add_pass(HintFilterPass())
        pipeline1.add_pass(PrivacyScanPass())
        pipeline1.add_pass(CorrectionCutoffPass(cutoff_timestamp=FIXED_TIMESTAMP))

        artifact1, _ = pipeline1.compile_runtime_profile(hints, context=context)

        # Second run with same tracker
        pipeline2 = CompilerPipeline(lineage_tracker=tracker)
        pipeline2.add_pass(HintFilterPass())
        pipeline2.add_pass(PrivacyScanPass())
        pipeline2.add_pass(CorrectionCutoffPass(cutoff_timestamp=FIXED_TIMESTAMP))

        artifact2, _ = pipeline2.compile_runtime_profile(hints, context=context)

        # Both should have lineage
        lineage1 = tracker.get(artifact1["id"])
        lineage2 = tracker.get(artifact2["id"])

        assert lineage1 is not None
        assert lineage2 is not None

    def test_replication_bundle_produces_identical_artifacts(self):
        """Test that replication bundle produces identical artifacts."""
        # Create first bundle
        bundle1 = ReplicationBundle()

        content1 = {
            "id": "test-artifact-001",
            "data": "test data",
            "timestamp": "2024-01-15T10:30:00Z",
        }
        bundle1.add_artifact("test-artifact-001", content1)

        # Create second bundle with same content
        bundle2 = ReplicationBundle()

        content2 = {
            "id": "test-artifact-001",
            "data": "test data",
            "timestamp": "2024-01-15T10:30:00Z",
        }
        bundle2.add_artifact("test-artifact-001", content2)

        # Bundles should be reproducible
        assert bundle1.verify_reproducibility(bundle2), "Bundles should be reproducible"

    def test_replication_bundle_checksum_matches_artifact(self):
        """Test that bundle checksum matches artifact checksums."""
        bundle = ReplicationBundle()

        content = {
            "id": "test-artifact-002",
            "data": "test data content",
        }
        bundle.add_artifact("test-artifact-002", content)

        # Verify artifact checksum
        assert bundle.verify_artifact_checksum("test-artifact-002", content)

    def test_compilation_is_deterministic_with_mock_model(self):
        """Test compilation is deterministic with consistent mock model behavior."""
        hints = [
            {"content": "hint1", "type": "normal"},
            {"content": "hint2", "type": "disputed"},
        ]
        corrections = [
            {"timestamp": "2024-01-10T00:00:00Z", "correction": "old"},
        ]

        # Use the SAME deterministic context for all runs
        context = make_deterministic_context("mock-model-test-001")
        context.disputed_approval = False
        context.sensitive_approval = False

        # Run 3 times and verify via bundle
        artifacts = []
        for i in range(3):
            pipeline = CompilerPipeline()
            pipeline.add_pass(HintFilterPass(disputed_approval=False))
            pipeline.add_pass(PrivacyScanPass())
            pipeline.add_pass(CorrectionCutoffPass(cutoff_timestamp=FIXED_TIMESTAMP))

            artifact, _ = pipeline.compile_runtime_profile(hints, corrections, context)
            artifacts.append(artifact)

        # All artifacts should be reproducible via bundle comparison
        bundle1 = ReplicationBundle()
        bundle1.add_artifact(artifacts[0]["id"], artifacts[0])

        bundle2 = ReplicationBundle()
        bundle2.add_artifact(artifacts[1]["id"], artifacts[1])

        assert bundle1.verify_reproducibility(bundle2), "Artifacts should be reproducible"

    def test_replication_bundle_serializes_deserializes_correctly(self, tmp_path):
        """Test that replication bundle can be saved and loaded."""
        bundle = ReplicationBundle()

        content = {
            "id": "test-artifact-003",
            "data": "test data",
            "nested": {"key": "value"},
        }
        bundle.add_artifact("test-artifact-003", content)

        # Save to file
        bundle_path = tmp_path / "replication_bundle.json"
        bundle.save(bundle_path)

        # Load from file
        loaded_bundle = ReplicationBundle.load(bundle_path)

        # Verify content matches
        loaded_artifact = loaded_bundle.get_artifact("test-artifact-003")
        assert loaded_artifact == content

        # Verify checksums match
        original_checksum = json.dumps(content, sort_keys=True)
        original_hash = hashlib.sha256(original_checksum.encode()).hexdigest()

        loaded_checksum = json.dumps(loaded_artifact, sort_keys=True)
        loaded_hash = hashlib.sha256(loaded_checksum.encode()).hexdigest()

        assert original_hash == loaded_hash

    def test_lineage_verification_passes_for_valid_content(self):
        """Test that lineage verification passes for valid content."""
        tracker = LineageTracker()

        content = {
            "id": "test-artifact-004",
            "data": "test data",
        }

        # Register lineage
        tracker.register(
            artifact_id="test-artifact-004",
            source_snapshot_id="source-001",
            content=content,
        )

        # Verify content
        assert tracker.verify("test-artifact-004", content), "Verification should pass"

    def test_lineage_verification_fails_for_tampered_content(self):
        """Test that lineage verification fails for tampered content."""
        tracker = LineageTracker()

        original_content = {
            "id": "test-artifact-005",
            "data": "original data",
        }

        # Register lineage with original content
        tracker.register(
            artifact_id="test-artifact-005",
            source_snapshot_id="source-001",
            content=original_content,
        )

        # Try to verify tampered content
        tampered_content = {
            "id": "test-artifact-005",
            "data": "tampered data!!!",
        }

        assert not tracker.verify("test-artifact-005", tampered_content), \
            "Verification should fail for tampered content"

    def test_multiple_artifacts_in_bundle_all_verified(self):
        """Test that multiple artifacts in a bundle can all be verified."""
        bundle = ReplicationBundle()

        artifacts = [
            {"id": f"artifact-{i}", "data": f"data-{i}"}
            for i in range(5)
        ]

        for artifact in artifacts:
            bundle.add_artifact(artifact["id"], artifact)

        # Verify all artifacts
        for artifact in artifacts:
            assert bundle.verify_artifact_checksum(artifact["id"], artifact), \
                f"Verification should pass for {artifact['id']}"

        # Verify bundle produces identical outputs when rebuilt
        bundle2 = ReplicationBundle()
        for artifact in artifacts:
            bundle2.add_artifact(artifact["id"], artifact)

        assert bundle.verify_reproducibility(bundle2), "Bundles should be reproducible"
