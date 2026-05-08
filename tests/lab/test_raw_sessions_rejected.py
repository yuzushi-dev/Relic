"""Tests for raw sessions rejection.

These tests verify that:
- Raw sessions are detected and rejected
- Datasets containing raw conversation data are blocked
- Privacy compliance is maintained
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from relic.lab.dataset_card import DatasetCard
from relic.lab.validate_dataset import (
    DatasetValidator,
    ValidationErrorType,
)


class TestRawSessionsRejected:
    """Tests for raw sessions detection and rejection."""

    def test_validator_detects_raw_conversations_directory(self) -> None:
        """Verify validator detects raw_conversations directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_path = Path(tmpdir)
            # Create a raw_conversations directory
            raw_dir = dataset_path / "raw_conversations"
            raw_dir.mkdir()
            (raw_dir / "session.json").write_text('{"messages": []}')

            # Add valid dataset_card
            card = DatasetCard(
                name="raw-test",
                description="Test with raw conversations",
                license="MIT",
                privacy_level="public",
                created_at="2024-01-01T00:00:00",
                source="test",
            )
            card.to_json_file(dataset_path / "dataset_card.json")

            validator = DatasetValidator(reject_raw_sessions=True)
            result = validator.validate(dataset_path)
            assert result.is_valid is False
            error_types = [e.error_type for e in result.errors]
            assert ValidationErrorType.RAW_SESSIONS_DETECTED in error_types

    def test_validator_detects_raw_sessions_file(self) -> None:
        """Verify validator detects raw_sessions file pattern."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_path = Path(tmpdir)
            # Create a file with raw_sessions in the name
            raw_file = dataset_path / "raw_sessions_data.json"
            raw_file.write_text('{"sessions": []}')

            # Add valid dataset_card
            card = DatasetCard(
                name="raw-file-test",
                description="Test with raw sessions file",
                license="MIT",
                privacy_level="public",
                created_at="2024-01-01T00:00:00",
                source="test",
            )
            card.to_json_file(dataset_path / "dataset_card.json")

            validator = DatasetValidator(reject_raw_sessions=True)
            result = validator.validate(dataset_path)
            assert result.is_valid is False
            error_types = [e.error_type for e in result.errors]
            assert ValidationErrorType.RAW_SESSIONS_DETECTED in error_types

    def test_validator_detects_provider_store(self) -> None:
        """Verify validator detects provider_store pattern."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_path = Path(tmpdir)
            # Create a file with provider_store in the name
            store_file = dataset_path / "provider_store_dump.json"
            store_file.write_text('{"stores": []}')

            # Add valid dataset_card
            card = DatasetCard(
                name="provider-test",
                description="Test with provider store",
                license="MIT",
                privacy_level="internal",
                created_at="2024-01-01T00:00:00",
                source="test",
            )
            card.to_json_file(dataset_path / "dataset_card.json")

            validator = DatasetValidator(reject_raw_sessions=True)
            result = validator.validate(dataset_path)
            assert result.is_valid is False
            error_types = [e.error_type for e in result.errors]
            assert ValidationErrorType.RAW_SESSIONS_DETECTED in error_types

    def test_validator_detects_conversation_dump(self) -> None:
        """Verify validator detects conversation_dump pattern."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_path = Path(tmpdir)
            # Create a file with conversation_dump in the name
            dump_file = dataset_path / "conversation_dump.jsonl"
            dump_file.write_text('{"message": "test"}\n')

            # Add valid dataset_card
            card = DatasetCard(
                name="dump-test",
                description="Test with conversation dump",
                license="MIT",
                privacy_level="public",
                created_at="2024-01-01T00:00:00",
                source="test",
            )
            card.to_json_file(dataset_path / "dataset_card.json")

            validator = DatasetValidator(reject_raw_sessions=True)
            result = validator.validate(dataset_path)
            assert result.is_valid is False
            error_types = [e.error_type for e in result.errors]
            assert ValidationErrorType.RAW_SESSIONS_DETECTED in error_types

    def test_validator_detects_session_log(self) -> None:
        """Verify validator detects session_log pattern."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_path = Path(tmpdir)
            # Create a file with session_log in the name
            log_file = dataset_path / "session_log.txt"
            log_file.write_text("session log content")

            # Add valid dataset_card
            card = DatasetCard(
                name="log-test",
                description="Test with session log",
                license="MIT",
                privacy_level="internal",
                created_at="2024-01-01T00:00:00",
                source="test",
            )
            card.to_json_file(dataset_path / "dataset_card.json")

            validator = DatasetValidator(reject_raw_sessions=True)
            result = validator.validate(dataset_path)
            assert result.is_valid is False
            error_types = [e.error_type for e in result.errors]
            assert ValidationErrorType.RAW_SESSIONS_DETECTED in error_types

    def test_validator_allows_clean_dataset(self) -> None:
        """Verify validator allows dataset without raw sessions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_path = Path(tmpdir)
            # Create clean data files
            (dataset_path / "train.json").write_text('[{"text": "clean data"}]')
            (dataset_path / "test.json").write_text('[{"text": "test data"}]')

            # Add valid dataset_card
            card = DatasetCard(
                name="clean-test",
                description="Test without raw sessions",
                license="MIT",
                privacy_level="public",
                created_at="2024-01-01T00:00:00",
                source="test",
            )
            card.to_json_file(dataset_path / "dataset_card.json")

            validator = DatasetValidator(reject_raw_sessions=True)
            result = validator.validate(dataset_path)
            assert result.is_valid is True
            error_types = [e.error_type for e in result.errors]
            assert ValidationErrorType.RAW_SESSIONS_DETECTED not in error_types

    def test_validator_with_raw_sessions_disabled(self) -> None:
        """Verify validator allows raw sessions when disabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_path = Path(tmpdir)
            # Create a file with raw_sessions in the name
            raw_file = dataset_path / "raw_sessions_data.json"
            raw_file.write_text('{"sessions": []}')

            # Add valid dataset_card
            card = DatasetCard(
                name="raw-file-test",
                description="Test with raw sessions file",
                license="MIT",
                privacy_level="public",
                created_at="2024-01-01T00:00:00",
                source="test",
            )
            card.to_json_file(dataset_path / "dataset_card.json")

            # Disable raw session rejection
            validator = DatasetValidator(reject_raw_sessions=False)
            result = validator.validate(dataset_path)
            # Should pass because rejection is disabled
            assert result.is_valid is True

    def test_detect_raw_sessions_returns_empty_for_clean_data(self) -> None:
        """Verify _detect_raw_sessions returns empty for clean data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_path = Path(tmpdir)
            (dataset_path / "train.json").write_text('[{"text": "data"}]')

            validator = DatasetValidator()
            indicators = validator._detect_raw_sessions(dataset_path)
            assert len(indicators) == 0

    def test_detect_raw_sessions_file_pattern(self) -> None:
        """Verify _detect_raw_sessions checks file patterns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_path = Path(tmpdir)
            (dataset_path / "raw_sessions.json").write_text('[]')

            validator = DatasetValidator()
            indicators = validator._detect_raw_sessions(dataset_path)
            assert len(indicators) > 0
            assert any("raw_sessions" in ind for ind in indicators)

    def test_validation_result_tracks_raw_session_errors(self) -> None:
        """Verify ValidationResult properly tracks raw session errors."""
        from relic.lab.validate_dataset import ValidationError, ValidationResult

        result = ValidationResult(is_valid=True, dataset_path="/test")
        result.add_error(ValidationError(
            error_type=ValidationErrorType.RAW_SESSIONS_DETECTED,
            message="Raw sessions found",
        ))

        assert result.is_valid is False
        assert len(result.errors) == 1
        assert result.errors[0].error_type == ValidationErrorType.RAW_SESSIONS_DETECTED
