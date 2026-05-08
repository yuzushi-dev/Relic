"""Tests for dataset_card requirement enforcement.

These tests verify that:
- dataset_card is required for every dataset
- Invalid or missing dataset cards are rejected
- Proper validation occurs before training/evaluation
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from relic.lab.dataset_card import (
    DatasetCard,
    DatasetCardSchema,
    require_dataset_card,
)
from relic.lab.validate_dataset import (
    DatasetValidator,
    ValidationErrorType,
)


class TestDatasetCardRequired:
    """Tests for dataset_card requirement."""

    def test_dataset_card_schema_has_required_fields(self) -> None:
        """Verify DatasetCardSchema defines required fields."""
        schema = DatasetCardSchema()
        assert "name" in schema.required_fields
        assert "description" in schema.required_fields
        assert "license" in schema.required_fields
        assert "privacy_level" in schema.required_fields
        assert "created_at" in schema.required_fields
        assert "source" in schema.required_fields

    def test_dataset_card_requires_name(self) -> None:
        """Verify DatasetCard rejects empty name."""
        with pytest.raises(ValueError, match="non-empty name"):
            DatasetCard(
                name="",
                description="Test description",
                license="MIT",
                privacy_level="public",
                created_at="2024-01-01T00:00:00",
                source="test",
            )

    def test_dataset_card_requires_description(self) -> None:
        """Verify DatasetCard rejects empty description."""
        with pytest.raises(ValueError, match="non-empty description"):
            DatasetCard(
                name="test-dataset",
                description="",
                license="MIT",
                privacy_level="public",
                created_at="2024-01-01T00:00:00",
                source="test",
            )

    def test_dataset_card_requires_valid_privacy_level(self) -> None:
        """Verify DatasetCard rejects invalid privacy levels."""
        with pytest.raises(ValueError, match="privacy_level must be"):
            DatasetCard(
                name="test-dataset",
                description="Test description",
                license="MIT",
                privacy_level="invalid",
                created_at="2024-01-01T00:00:00",
                source="test",
            )

    def test_dataset_card_valid_public(self) -> None:
        """Verify DatasetCard accepts 'public' privacy level."""
        card = DatasetCard(
            name="test-public",
            description="A test dataset",
            license="MIT",
            privacy_level="public",
            created_at="2024-01-01T00:00:00",
            source="test",
        )
        assert card.privacy_level == "public"
        assert card.is_valid() is True

    def test_dataset_card_valid_internal(self) -> None:
        """Verify DatasetCard accepts 'internal' privacy level."""
        card = DatasetCard(
            name="test-internal",
            description="An internal dataset",
            license="proprietary",
            privacy_level="internal",
            created_at="2024-01-01T00:00:00",
            source="test",
        )
        assert card.privacy_level == "internal"
        assert card.is_valid() is True

    def test_dataset_card_valid_confidential(self) -> None:
        """Verify DatasetCard accepts 'confidential' privacy level."""
        card = DatasetCard(
            name="test-confidential",
            description="A confidential dataset",
            license="proprietary",
            privacy_level="confidential",
            created_at="2024-01-01T00:00:00",
            source="test",
        )
        assert card.privacy_level == "confidential"
        assert card.is_valid() is True

    def test_dataset_card_to_dict_roundtrip(self) -> None:
        """Verify DatasetCard serialization roundtrip."""
        original = DatasetCard(
            name="roundtrip-test",
            description="Test roundtrip",
            license="MIT",
            privacy_level="public",
            created_at="2024-01-01T00:00:00",
            source="unit-test",
        )
        data = original.to_dict()
        restored = DatasetCard.from_dict(data)
        assert restored.name == original.name
        assert restored.description == original.description
        assert restored.privacy_level == original.privacy_level

    def test_dataset_card_file_roundtrip(self) -> None:
        """Verify DatasetCard file I/O roundtrip."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "dataset_card.json"
            card = DatasetCard(
                name="file-test",
                description="Test file I/O",
                license="MIT",
                privacy_level="internal",
                created_at="2024-01-01T00:00:00",
                source="unit-test",
            )
            card.to_json_file(path)
            assert path.exists()

            restored = DatasetCard.from_json_file(path)
            assert restored.name == card.name
            assert restored.description == card.description

    def test_dataset_card_missing_file_raises(self) -> None:
        """Verify loading missing file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            DatasetCard.from_json_file("/nonexistent/path/dataset_card.json")

    def test_is_valid_with_all_required_fields(self) -> None:
        """Verify is_valid returns True when all required fields present."""
        card = DatasetCard(
            name="valid-card",
            description="Valid description",
            license="MIT",
            privacy_level="public",
            created_at="2024-01-01T00:00:00",
            source="test",
        )
        assert card.is_valid() is True


class TestDatasetValidator:
    """Tests for DatasetValidator."""

    def test_validator_rejects_missing_dataset_card(self) -> None:
        """Verify validator rejects dataset without dataset_card.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_path = Path(tmpdir)
            validator = DatasetValidator()
            result = validator.validate(dataset_path)
            assert result.is_valid is False
            error_types = [e.error_type for e in result.errors]
            assert ValidationErrorType.MISSING_DATASET_CARD in error_types

    def test_validator_accepts_valid_dataset_card(self) -> None:
        """Verify validator accepts dataset with valid dataset_card."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_path = Path(tmpdir)
            card = DatasetCard(
                name="valid-test",
                description="Valid test dataset",
                license="MIT",
                privacy_level="public",
                created_at="2024-01-01T00:00:00",
                source="test",
            )
            card.to_json_file(dataset_path / "dataset_card.json")

            validator = DatasetValidator()
            result = validator.validate(dataset_path)
            assert result.is_valid is True
            assert len(result.errors) == 0

    def test_validator_rejects_invalid_json(self) -> None:
        """Verify validator rejects invalid JSON in dataset_card."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_path = Path(tmpdir)
            card_path = dataset_path / "dataset_card.json"
            card_path.write_text("{ invalid json }")

            validator = DatasetValidator()
            result = validator.validate(dataset_path)
            assert result.is_valid is False
            error_types = [e.error_type for e in result.errors]
            assert ValidationErrorType.INVALID_DATASET_CARD in error_types

    def test_validator_rejects_missing_required_fields(self) -> None:
        """Verify validator rejects dataset_card with missing fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset_path = Path(tmpdir)
            card_path = dataset_path / "dataset_card.json"
            card_path.write_text(json.dumps({
                "name": "incomplete-card",
                # Missing description, license, etc.
            }))

            validator = DatasetValidator()
            result = validator.validate(dataset_path)
            assert result.is_valid is False
            error_types = [e.error_type for e in result.errors]
            assert ValidationErrorType.MISSING_REQUIRED_FIELD in error_types


class TestRequireDatasetCardDecorator:
    """Tests for require_dataset_card decorator."""

    def test_decorator_rejects_none(self) -> None:
        """Verify decorator rejects None dataset_card."""
        @require_dataset_card
        def func(dataset_card=None):
            return dataset_card

        with pytest.raises(ValueError, match="dataset_card is required"):
            func()

    def test_decorator_rejects_invalid_card(self) -> None:
        """Verify decorator rejects invalid DatasetCard."""
        @require_dataset_card
        def func(dataset_card=None):
            return dataset_card

        with pytest.raises(ValueError, match="dataset_card is invalid"):
            func(dataset_card=DatasetCard(
                name="",
                description="",
                license="MIT",
                privacy_level="public",
                created_at="2024-01-01T00:00:00",
                source="test",
            ))

    def test_decorator_accepts_valid_card(self) -> None:
        """Verify decorator accepts valid DatasetCard."""
        @require_dataset_card
        def func(dataset_card=None):
            return "success"

        card = DatasetCard(
            name="valid-card",
            description="Valid description",
            license="MIT",
            privacy_level="public",
            created_at="2024-01-01T00:00:00",
            source="test",
        )
        result = func(dataset_card=card)
        assert result == "success"
