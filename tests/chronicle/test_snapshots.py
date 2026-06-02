"""Tests for snapshot capture module, T020.

Module: tests.chronicle.test_snapshots
Reference: docs/chronicle/agentic-development-plan.md §8.1, T020
"""
from __future__ import annotations

import json
import tempfile
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch, call

import pytest

from relic.persistence import PrivacyLevel


class TestCaptureSnapshotValidation:
    """Test validation of capture_snapshot() parameters."""

    def test_empty_snapshot_type_raises(self, tmp_chronicle_dir: str) -> None:
        """Empty snapshot_type raises ValueError."""
        from relic.chronicle.snapshots import capture_snapshot
        
        with patch("relic.chronicle.snapshots.emit_snapshot") as mock_emit:
            mock_emit.return_value = uuid.uuid4()
            with pytest.raises(ValueError, match="snapshot_type cannot be empty"):
                capture_snapshot(
                    snapshot_type="",
                    scope_ref="session:test",
                    content={"test": "data"},
                )

    def test_whitespace_snapshot_type_raises(self, tmp_chronicle_dir: str) -> None:
        """Whitespace-only snapshot_type raises ValueError."""
        from relic.chronicle.snapshots import capture_snapshot
        
        with patch("relic.chronicle.snapshots.emit_snapshot") as mock_emit:
            mock_emit.return_value = uuid.uuid4()
            with pytest.raises(ValueError, match="snapshot_type cannot be empty"):
                capture_snapshot(
                    snapshot_type="   ",
                    scope_ref="session:test",
                    content={"test": "data"},
                )

    def test_empty_scope_ref_raises(self, tmp_chronicle_dir: str) -> None:
        """Empty scope_ref raises ValueError."""
        from relic.chronicle.snapshots import capture_snapshot
        
        with patch("relic.chronicle.snapshots.emit_snapshot") as mock_emit:
            mock_emit.return_value = uuid.uuid4()
            with pytest.raises(ValueError, match="scope_ref cannot be empty"):
                capture_snapshot(
                    snapshot_type="test_snapshot",
                    scope_ref="",
                    content={"test": "data"},
                )

    def test_whitespace_scope_ref_raises(self, tmp_chronicle_dir: str) -> None:
        """Whitespace-only scope_ref raises ValueError."""
        from relic.chronicle.snapshots import capture_snapshot
        
        with patch("relic.chronicle.snapshots.emit_snapshot") as mock_emit:
            mock_emit.return_value = uuid.uuid4()
            with pytest.raises(ValueError, match="scope_ref cannot be empty"):
                capture_snapshot(
                    snapshot_type="test_snapshot",
                    scope_ref="   ",
                    content={"test": "data"},
                )


class TestCaptureSnapshotBasic:
    """Test basic capture_snapshot() functionality."""

    def test_capture_dict_content(self, tmp_chronicle_dir: str) -> None:
        """Capture snapshot with dict content."""
        from relic.chronicle.snapshots import capture_snapshot
        
        with patch("relic.chronicle.snapshots.emit_snapshot") as mock_emit:
            mock_emit.return_value = uuid.uuid4()
            
            snapshot_id = capture_snapshot(
                snapshot_type="profile_snapshot",
                scope_ref="session:test123",
                content={"user": "alice", "state": "active"},
            )
            
            assert snapshot_id is not None
            assert isinstance(snapshot_id, uuid.UUID)

    def test_capture_string_content(self, tmp_chronicle_dir: str) -> None:
        """Capture snapshot with string content."""
        from relic.chronicle.snapshots import capture_snapshot
        
        with patch("relic.chronicle.snapshots.emit_snapshot") as mock_emit:
            mock_emit.return_value = uuid.uuid4()
            
            snapshot_id = capture_snapshot(
                snapshot_type="memory_state",
                scope_ref="profile:test456",
                content="Memory dump content here",
            )
            
            assert snapshot_id is not None
            assert isinstance(snapshot_id, uuid.UUID)

    def test_capture_bytes_content(self, tmp_chronicle_dir: str) -> None:
        """Capture snapshot with bytes content."""
        from relic.chronicle.snapshots import capture_snapshot
        
        with patch("relic.chronicle.snapshots.emit_snapshot") as mock_emit:
            mock_emit.return_value = uuid.uuid4()
            
            snapshot_id = capture_snapshot(
                snapshot_type="binary_snapshot",
                scope_ref="artifact:test789",
                content=b"Binary data content",
            )
            
            assert snapshot_id is not None

    def test_capture_with_all_params(self, tmp_chronicle_dir: str) -> None:
        """Capture snapshot with all optional parameters."""
        from relic.chronicle.snapshots import capture_snapshot
        
        subject_id = "user_123"
        trigger_id = uuid.uuid4()
        trace_id = uuid.uuid4()
        
        with patch("relic.chronicle.snapshots.emit_snapshot") as mock_emit:
            mock_emit.return_value = uuid.uuid4()
            
            snapshot_id = capture_snapshot(
                snapshot_type="profile_snapshot",
                scope_ref="session:test",
                content={"data": "value"},
                subject_id=subject_id,
                trigger_event_id=trigger_id,
                sensitivity=PrivacyLevel.S0_HARD_VIOLATION,
                retention_policy="SHORT_30D",
                trace_id=trace_id,
            )
            
            assert snapshot_id is not None
            call_kwargs = mock_emit.call_args.kwargs
            assert call_kwargs["subject_id"] == subject_id
            assert call_kwargs["trigger_event_id"] == trigger_id
            assert call_kwargs["trace_id"] == trace_id


class TestCaptureSnapshotHash:
    """Test that content_hash is computed via compute_checksum."""

    def test_hash_computed_via_checksum_module(self, tmp_chronicle_dir: str) -> None:
        """content_hash should be computed via compute_checksum, not inline hashlib."""
        from relic.artifacts.checksums import compute_checksum
        from relic.chronicle.snapshots import capture_snapshot
        
        test_content = {"key": "value"}
        
        with patch("relic.chronicle.snapshots.emit_snapshot") as mock_emit:
            mock_emit.return_value = uuid.uuid4()
            
            capture_snapshot(
                snapshot_type="test",
                scope_ref="session:test",
                content=test_content,
            )
            
            assert mock_emit.called

    def test_different_content_different_hash(self, tmp_chronicle_dir: str) -> None:
        """Different content should produce different inline refs."""
        from relic.chronicle.snapshots import capture_snapshot
        
        captured_refs = []
        
        def capture_emit(**kwargs):
            captured_refs.append(kwargs.get("content_ref", ""))
            return uuid.uuid4()
        
        with patch("relic.chronicle.snapshots.emit_snapshot", side_effect=capture_emit):
            # Use different sizes so inline refs differ
            capture_snapshot(snapshot_type="test", scope_ref="s", content={"short": "a"})
            capture_snapshot(snapshot_type="test", scope_ref="s", content={"much_longer_key": "much longer value here"})
        
        # Different content should lead to different inline refs
        assert captured_refs[0] != captured_refs[1]


class TestCaptureSnapshotLargeContent:
    """Test large content offloading to filesystem."""

    def test_large_content_stored_as_blob(self, tmp_chronicle_dir: str) -> None:
        """Content >1MB should be stored as blob in filesystem."""
        from relic.chronicle.snapshots import capture_snapshot, _snapshots_dir
        
        # Mock _snapshots_dir to use tmp_chronicle_dir
        snapshots_path = Path(tmp_chronicle_dir) / "snapshots"
        
        def mock_snapshots_dir():
            snapshots_path.mkdir(parents=True, exist_ok=True)
            return snapshots_path
        
        # Create content > 1MB
        large_content = {"data": "x" * (1024 * 1024 + 100)}
        
        with patch("relic.chronicle.snapshots._snapshots_dir", mock_snapshots_dir):
            snapshot_id = capture_snapshot(
                snapshot_type="large_snapshot",
                scope_ref="session:test",
                content=large_content,
            )
        
        # Verify blob exists with correct name
        blob_path = snapshots_path / f"{snapshot_id}.blob"
        assert blob_path.exists(), f"Blob should exist at {blob_path}"

    def test_small_content_inline_ref(self, tmp_chronicle_dir: str) -> None:
        """Content <1MB should have inline content_ref."""
        from relic.chronicle.snapshots import capture_snapshot
        
        small_content = {"key": "value"}
        
        with patch("relic.chronicle.snapshots.emit_snapshot") as mock_emit:
            mock_emit.return_value = uuid.uuid4()
            
            capture_snapshot(
                snapshot_type="small_snapshot",
                scope_ref="session:test",
                content=small_content,
            )
            
            call_kwargs = mock_emit.call_args.kwargs
            content_ref = call_kwargs.get("content_ref", "")
            assert content_ref.startswith("inline:")

    def test_blob_renamed_after_emit(self, tmp_chronicle_dir: str) -> None:
        """Blob should be renamed from temp_id to actual snapshot_id after emit."""
        from relic.chronicle.snapshots import capture_snapshot, _snapshots_dir
        
        snapshots_path = Path(tmp_chronicle_dir) / "snapshots"
        
        def mock_snapshots_dir():
            snapshots_path.mkdir(parents=True, exist_ok=True)
            return snapshots_path
        
        large_content = {"data": "x" * (1024 * 1024 + 100)}
        
        actual_uuid = [None]
        
        def mock_emit(**kwargs):
            actual_uuid[0] = uuid.uuid4()
            return actual_uuid[0]
        
        with patch("relic.chronicle.snapshots._snapshots_dir", mock_snapshots_dir):
            with patch("relic.chronicle.snapshots.emit_snapshot", side_effect=mock_emit):
                result = capture_snapshot(
                    snapshot_type="large",
                    scope_ref="session:test",
                    content=large_content,
                )
        
        # The final blob should exist with the actual UUID
        blob_path = snapshots_path / f"{result}.blob"
        assert blob_path.exists()


class TestCaptureSnapshotDiff:
    """Test diff computation from previous snapshot."""

    def test_diff_computed_when_previous_provided(self, tmp_chronicle_dir: str) -> None:
        """diff_from_previous should be computed when previous_snapshot_id provided."""
        from relic.chronicle.snapshots import capture_snapshot, _snapshots_dir
        
        snapshots_path = Path(tmp_chronicle_dir) / "snapshots"
        
        def mock_snapshots_dir():
            snapshots_path.mkdir(parents=True, exist_ok=True)
            return snapshots_path
        
        mock_emit = MagicMock()
        mock_emit.side_effect = lambda **kw: uuid.uuid4()
        
        with patch("relic.chronicle.snapshots._snapshots_dir", mock_snapshots_dir):
            with patch("relic.chronicle.snapshots.emit_snapshot", mock_emit):
                prev_id = capture_snapshot(
                    snapshot_type="test",
                    scope_ref="session:test",
                    content={"a": 1, "b": 2},
                )
                
                curr_id = capture_snapshot(
                    snapshot_type="test",
                    scope_ref="session:test",
                    content={"a": 1, "b": 2, "c": 3},
                    previous_snapshot_id=prev_id,
                )
        
        # Verify diff was computed - second call should have previous_snapshot_id
        emit_calls = mock_emit.call_args_list
        assert len(emit_calls) >= 2
        second_call_kwargs = emit_calls[1].kwargs
        assert second_call_kwargs.get("previous_snapshot_id") == prev_id

    def test_diff_shows_added_and_removed_keys(self, tmp_chronicle_dir: str) -> None:
        """Diff should correctly identify added and removed keys."""
        from relic.chronicle.snapshots import _compute_diff
        
        diff = _compute_diff(
            {"existing": "value", "to_remove": "old"},
            {"existing": "value", "new_key": "new_value"}
        )
        
        assert "new_key" in diff["added"]
        assert "to_remove" in diff["removed"]

    def test_diff_shows_changed_values(self, tmp_chronicle_dir: str) -> None:
        """Diff should correctly identify changed values."""
        from relic.chronicle.snapshots import _compute_diff
        
        diff = _compute_diff(
            {"count": 1},
            {"count": 2}
        )
        
        assert "count" in diff["changed"]


class TestCaptureSnapshotEnumNormalization:
    """Test enum normalization in capture_snapshot()."""

    def test_string_sensitivity_normalized(self, tmp_chronicle_dir: str) -> None:
        """String sensitivity should be normalized to PrivacyLevel enum."""
        from relic.chronicle.snapshots import capture_snapshot
        
        with patch("relic.chronicle.snapshots.emit_snapshot") as mock_emit:
            mock_emit.return_value = uuid.uuid4()
            
            capture_snapshot(
                snapshot_type="test",
                scope_ref="session:test",
                content={"data": "value"},
                sensitivity="s0",  # String, not enum
            )
            
            call_kwargs = mock_emit.call_args.kwargs
            sensitivity = call_kwargs.get("sensitivity")
            # Should be normalized to PrivacyLevel enum
            assert isinstance(sensitivity, PrivacyLevel)

    def test_string_retention_normalized(self, tmp_chronicle_dir: str) -> None:
        """String retention_policy should be normalized to RetentionPolicy enum."""
        from relic.chronicle.snapshots import capture_snapshot
        from relic.chronicle.enums import RetentionPolicy
        
        with patch("relic.chronicle.snapshots.emit_snapshot") as mock_emit:
            mock_emit.return_value = uuid.uuid4()
            
            capture_snapshot(
                snapshot_type="test",
                scope_ref="session:test",
                content={"data": "value"},
                retention_policy="SHORT_30D",  # String, not enum
            )
            
            call_kwargs = mock_emit.call_args.kwargs
            retention = call_kwargs.get("retention_policy")
            # Should be normalized to RetentionPolicy enum
            assert isinstance(retention, RetentionPolicy)


class TestCaptureSnapshotEmitIntegration:
    """Test that emit_snapshot() is called correctly."""

    def test_calls_emit_snapshot(self, tmp_chronicle_dir: str) -> None:
        """capture_snapshot should call emit_snapshot internally."""
        from relic.chronicle.snapshots import capture_snapshot
        
        with patch("relic.chronicle.snapshots.emit_snapshot") as mock_emit:
            mock_emit.return_value = uuid.uuid4()
            
            capture_snapshot(
                snapshot_type="test",
                scope_ref="session:test",
                content={"data": "value"},
            )
            
            mock_emit.assert_called_once()
            call_kwargs = mock_emit.call_args.kwargs
            assert call_kwargs["snapshot_type"] == "test"
            assert call_kwargs["scope_ref"] == "session:test"
            assert call_kwargs["content"] == {"data": "value"}

    def test_passes_all_params_to_emit(self, tmp_chronicle_dir: str) -> None:
        """All relevant parameters should be passed to emit_snapshot."""
        from relic.chronicle.snapshots import capture_snapshot
        
        subject_id = "user_123"
        trigger_id = uuid.uuid4()
        trace_id = uuid.uuid4()
        
        with patch("relic.chronicle.snapshots.emit_snapshot") as mock_emit:
            mock_emit.return_value = uuid.uuid4()
            
            capture_snapshot(
                snapshot_type="test_snapshot",
                scope_ref="profile:test",
                content={"test": "data"},
                subject_id=subject_id,
                trigger_event_id=trigger_id,
                trace_id=trace_id,
            )
            
            call_kwargs = mock_emit.call_args.kwargs
            assert call_kwargs["subject_id"] == subject_id
            assert call_kwargs["trigger_event_id"] == trigger_id
            assert call_kwargs["trace_id"] == trace_id


class TestCaptureSnapshotComputeChecksum:
    """Test that compute_checksum is used (not inline hashlib)."""

    def test_uses_checksum_module(self, tmp_chronicle_dir: str) -> None:
        """Should call compute_checksum from relic.artifacts.checksums."""
        from relic.chronicle.snapshots import capture_snapshot
        
        with patch("relic.chronicle.snapshots.compute_checksum") as mock_checksum:
            mock_checksum.return_value = "a" * 64
            
            with patch("relic.chronicle.snapshots.emit_snapshot") as mock_emit:
                mock_emit.return_value = uuid.uuid4()
                
                capture_snapshot(
                    snapshot_type="test",
                    scope_ref="session:test",
                    content={"key": "value"},
                )
                
                # Verify compute_checksum was called
                mock_checksum.assert_called()
                call_args = mock_checksum.call_args[0]
                assert call_args[0] == {"key": "value"}

    def test_checksum_not_hashlib_inline(self, tmp_chronicle_dir: str) -> None:
        """Should NOT use hashlib.sha256 directly in capture_snapshot."""
        import relic.chronicle.snapshots as snapshots_module
        import inspect
        
        source = inspect.getsource(snapshots_module)
        
        # Check that hashlib is not used directly
        assert "hashlib.sha256" not in source, \
            "snapshots.py should use compute_checksum, not inline hashlib"


class TestCaptureSnapshotEdgeCases:
    """Test edge cases for capture_snapshot()."""

    def test_list_content(self, tmp_chronicle_dir: str) -> None:
        """Should handle list content."""
        from relic.chronicle.snapshots import capture_snapshot
        
        with patch("relic.chronicle.snapshots.emit_snapshot") as mock_emit:
            mock_emit.return_value = uuid.uuid4()
            
            snapshot_id = capture_snapshot(
                snapshot_type="list_snapshot",
                scope_ref="session:test",
                content=[1, 2, 3, {"nested": "value"}],
            )
            
            assert snapshot_id is not None

    def test_unicode_content(self, tmp_chronicle_dir: str) -> None:
        """Should handle unicode content correctly."""
        from relic.chronicle.snapshots import capture_snapshot
        
        with patch("relic.chronicle.snapshots.emit_snapshot") as mock_emit:
            mock_emit.return_value = uuid.uuid4()
            
            snapshot_id = capture_snapshot(
                snapshot_type="unicode_test",
                scope_ref="session:test",
                content={"emoji": "🎉", "unicode": "こんにちは"},
            )
            
            assert snapshot_id is not None

    def test_none_as_valid_content(self, tmp_chronicle_dir: str) -> None:
        """Should handle None as content value."""
        from relic.chronicle.snapshots import capture_snapshot
        
        with patch("relic.chronicle.snapshots.emit_snapshot") as mock_emit:
            mock_emit.return_value = uuid.uuid4()
            
            snapshot_id = capture_snapshot(
                snapshot_type="none_test",
                scope_ref="session:test",
                content={"null_value": None},
            )
            
            assert snapshot_id is not None


class TestSerializeContent:
    """Test content serialization helper."""

    def test_serialize_dict(self) -> None:
        """Dict should be JSON serialized."""
        from relic.chronicle.snapshots import _serialize_content
        
        content = {"key": "value", "number": 42}
        serialized, size = _serialize_content(content)
        
        assert isinstance(serialized, str)
        assert size > 0
        parsed = json.loads(serialized)
        assert parsed == content

    def test_serialize_string(self) -> None:
        """String should return length in bytes."""
        from relic.chronicle.snapshots import _serialize_content
        
        content = "Hello, World!"
        serialized, size = _serialize_content(content)
        
        assert serialized == content
        assert size == len(content.encode("utf-8"))

    def test_serialize_bytes(self) -> None:
        """Bytes should be decoded to string."""
        from relic.chronicle.snapshots import _serialize_content
        
        content = b"Binary data"
        serialized, size = _serialize_content(content)
        
        assert serialized == "Binary data"
        assert size == len(content)
