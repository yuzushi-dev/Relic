"""Tests for replication bundle module."""

import zipfile

import pytest

from relic.eval.replication_bundle import (
    ReplicationBundle,
    TraceEntry,
    build_bundle,
    create_trace_entry,
    load_bundle,
)


class TestTraceEntry:
    """Tests for TraceEntry dataclass."""

    def test_create_trace_entry(self):
        """Test creating a trace entry."""
        entry = create_trace_entry(
            scenario_id="test_1",
            prompt="Test prompt",
            response="Test response",
        )

        assert entry.scenario_id == "test_1"
        assert entry.checksum is not None
        assert len(entry.checksum) == 64  # SHA-256 hex length

    def test_trace_entry_to_dict(self):
        """Test serializing trace entry."""
        entry = create_trace_entry(
            scenario_id="test_1",
            prompt="Test prompt",
            response="Test response",
        )

        data = entry.to_dict()
        assert data["scenario_id"] == "test_1"
        assert "checksum" in data

    def test_trace_entry_from_dict(self):
        """Test deserializing trace entry."""
        data = {
            "scenario_id": "test_1",
            "prompt": "Test prompt",
            "response": "Test response",
            "checksum": "abc123",
            "metadata": {},
        }

        entry = TraceEntry.from_dict(data)
        assert entry.scenario_id == "test_1"
        assert entry.checksum == "abc123"


class TestReplicationBundle:
    """Tests for ReplicationBundle class."""

    def test_create_bundle(self):
        """Test creating a replication bundle."""
        bundle = ReplicationBundle(
            bundle_id="test_bundle",
            created_at="2024-01-01T00:00:00Z",
        )

        assert bundle.bundle_id == "test_bundle"
        assert len(bundle.traces) == 0

    def test_bundle_to_dict(self):
        """Test serializing bundle."""
        bundle = ReplicationBundle(
            bundle_id="test_bundle",
            created_at="2024-01-01T00:00:00Z",
        )

        data = bundle.to_dict()
        assert data["bundle_id"] == "test_bundle"
        assert "traces" in data

    def test_create_checksum(self):
        """Test checksum creation."""
        bundle = ReplicationBundle(
            bundle_id="test_bundle",
            created_at="2024-01-01T00:00:00Z",
        )

        checksum = bundle.create_checksum("test content")
        assert len(checksum) == 64

    def test_verify_checksums(self):
        """Test checksum verification."""
        entry = create_trace_entry(
            scenario_id="test_1",
            prompt="Test prompt",
            response="Test response",
        )

        bundle = ReplicationBundle(
            bundle_id="test_bundle",
            created_at="2024-01-01T00:00:00Z",
            traces=[entry],
        )

        verification = bundle.verify_checksums()
        assert verification["test_1"] is True

    def test_verify_checksums_fails(self):
        """Test checksum verification failure."""
        entry = TraceEntry(
            scenario_id="test_1",
            prompt="Test prompt",
            response="Test response",
            checksum="invalid_checksum",
        )

        bundle = ReplicationBundle(
            bundle_id="test_bundle",
            created_at="2024-01-01T00:00:00Z",
            traces=[entry],
        )

        verification = bundle.verify_checksums()
        assert verification["test_1"] is False

    def test_generate_manifest(self):
        """Test manifest generation."""
        bundle = ReplicationBundle(
            bundle_id="test_bundle",
            created_at="2024-01-01T00:00:00Z",
        )

        manifest = bundle.generate_manifest()

        assert manifest["bundle_id"] == "test_bundle"
        assert manifest["trace_count"] == 0
        assert "traces_checksum" in manifest

    def test_to_zip(self, tmp_path):
        """Test exporting bundle as ZIP."""
        entry = create_trace_entry(
            scenario_id="test_1",
            prompt="Test prompt",
            response="Test response",
        )

        bundle = ReplicationBundle(
            bundle_id="test_bundle",
            created_at="2024-01-01T00:00:00Z",
            traces=[entry],
            policy_snapshot={"privacy_policy": "default"},
            report={"summary": {"total": 10}},
        )

        zip_path = tmp_path / "test_bundle.zip"
        result = bundle.to_zip(zip_path)

        assert result.exists()

        # Verify ZIP contents
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            assert "manifest.json" in names
            assert "traces.jsonl" in names
            assert "policy_snapshot.json" in names
            assert "report.json" in names

    def test_to_zip_rejects_raw_private_trace_content(self, tmp_path):
        """Public bundle export refuses obvious raw private trace text."""
        entry = TraceEntry(
            scenario_id="test_1",
            prompt="RAW_PRIVATE_PROMPT",
            response="RAW_PRIVATE_RESPONSE",
            checksum="bad",
        )
        bundle = ReplicationBundle(
            bundle_id="test_bundle",
            created_at="2024-01-01T00:00:00Z",
            traces=[entry],
        )

        with pytest.raises(ValueError) as exc_info:
            bundle.to_zip(tmp_path / "test_bundle.zip")

        assert "raw private" in str(exc_info.value).lower()


class TestBuildBundle:
    """Tests for build_bundle function."""

    def test_build_minimal_bundle(self):
        """Test building a minimal bundle."""
        bundle = build_bundle()

        assert bundle.bundle_id.startswith("replication_bundle_")
        assert len(bundle.traces) == 0

    def test_build_bundle_with_traces(self):
        """Test building bundle with traces."""
        traces = [
            create_trace_entry("test_1", "Prompt 1", "Response 1"),
            create_trace_entry("test_2", "Prompt 2", "Response 2"),
        ]

        bundle = build_bundle(traces=traces)

        assert len(bundle.traces) == 2
        assert bundle.manifest["trace_count"] == 2

    def test_build_bundle_with_policy_snapshot(self):
        """Test building bundle with policy snapshot."""
        policy = {"privacy_policy": "strict", "correction_enabled": True}

        bundle = build_bundle(policy_snapshot=policy)

        assert bundle.policy_snapshot == policy
        assert bundle.manifest["has_policy_snapshot"] is True

    def test_build_bundle_to_zip(self, tmp_path):
        """Test building bundle and exporting to ZIP."""
        build_bundle(
            traces=[
                create_trace_entry("test_1", "Prompt", "Response"),
            ],
            bundle_id="test_bundle",
            output_dir=tmp_path,
        )

        zip_path = tmp_path / "test_bundle.zip"
        assert zip_path.exists()


class TestLoadBundle:
    """Tests for load_bundle function."""

    def test_load_bundle_roundtrip(self, tmp_path):
        """Test loading a bundle from ZIP."""
        # Create bundle
        traces = [
            create_trace_entry("test_1", "Prompt 1", "Response 1"),
            create_trace_entry("test_2", "Prompt 2", "Response 2"),
        ]

        policy = {"test_policy": True}
        report = {"summary": {"passed": 5}}

        original = build_bundle(
            traces=traces,
            policy_snapshot=policy,
            report=report,
            bundle_id="roundtrip_test",
        )

        zip_path = tmp_path / "roundtrip_test.zip"
        original.to_zip(zip_path)

        # Load bundle
        loaded = load_bundle(zip_path)

        assert loaded.bundle_id == "roundtrip_test"
        assert len(loaded.traces) == 2
        assert loaded.policy_snapshot == policy
        assert loaded.report == report

    def test_load_nonexistent_bundle(self):
        """Test loading non-existent bundle."""
        with pytest.raises(FileNotFoundError):
            load_bundle("/nonexistent/path.zip")
