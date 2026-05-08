"""Dataset validation module for adapter training labs.

This module provides validation for datasets used in adapter training,
ensuring raw sessions are rejected and privacy compliance is maintained.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


class ValidationErrorType(Enum):
    """Types of validation errors."""

    MISSING_DATASET_CARD = "missing_dataset_card"
    INVALID_DATASET_CARD = "invalid_dataset_card"
    RAW_SESSIONS_DETECTED = "raw_sessions_detected"
    MISSING_REQUIRED_FIELD = "missing_required_field"
    INVALID_PRIVACY_LEVEL = "invalid_privacy_level"
    SCHEMA_HASH_MISMATCH = "schema_hash_mismatch"


@dataclass
class ValidationError:
    """Represents a validation error."""

    error_type: ValidationErrorType
    message: str
    field: str | None = None
    severity: str = "error"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "error_type": self.error_type.value,
            "message": self.message,
            "field": self.field,
            "severity": self.severity,
        }


@dataclass
class ValidationResult:
    """Result of dataset validation.

    Attributes:
        is_valid: Whether validation passed.
        errors: List of validation errors.
        warnings: List of non-critical warnings.
        dataset_path: Path that was validated.
    """

    is_valid: bool
    errors: list[ValidationError] = None
    warnings: list[str] = None
    dataset_path: str = ""

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for reporting."""
        return {
            "is_valid": self.is_valid,
            "errors": [e.to_dict() for e in self.errors],
            "warnings": self.warnings,
            "dataset_path": self.dataset_path,
        }

    def add_error(self, error: ValidationError) -> None:
        """Add an error and mark validation as failed."""
        self.errors.append(error)
        self.is_valid = False


class DatasetValidator:
    """Validates datasets for adapter training.

    This validator ensures:
    - dataset_card is present for every dataset
    - Raw sessions are rejected
    - Privacy levels are valid
    - Required fields are present
    """

    def __init__(self, reject_raw_sessions: bool = True) -> None:
        """Initialize validator.

        Args:
            reject_raw_sessions: If True, raw session data is rejected.
        """
        self.reject_raw_sessions = reject_raw_sessions
        self._validation_count = 0

    def validate(
        self,
        dataset_path: Path | str,
        dataset_card_path: Path | str | None = None,
    ) -> ValidationResult:
        """Validate a dataset.

        Args:
            dataset_path: Path to the dataset directory or file.
            dataset_card_path: Optional path to dataset_card.json.
                                If None, looks for dataset_card.json in same directory.

        Returns:
            ValidationResult with pass/fail and any errors.
        """
        self._validation_count += 1
        dataset_path = Path(dataset_path)
        result = ValidationResult(
            is_valid=True,
            dataset_path=str(dataset_path),
        )

        # Check for dataset_card
        if dataset_card_path is None:
            if dataset_path.is_file():
                dataset_card_path = dataset_path.parent / "dataset_card.json"
            else:
                dataset_card_path = dataset_path / "dataset_card.json"
        else:
            dataset_card_path = Path(dataset_card_path)

        if not dataset_card_path.exists():
            result.add_error(ValidationError(
                error_type=ValidationErrorType.MISSING_DATASET_CARD,
                message="dataset_card.json is required for every dataset",
                field="dataset_card",
            ))
            return result

        # Load and validate dataset_card
        try:
            with open(dataset_card_path) as f:
                card_data = json.load(f)
        except json.JSONDecodeError as e:
            result.add_error(ValidationError(
                error_type=ValidationErrorType.INVALID_DATASET_CARD,
                message=f"Invalid JSON in dataset_card: {e}",
                field="dataset_card",
            ))
            return result

        # Validate required fields
        required_fields = ("name", "description", "license", "privacy_level", "created_at", "source")
        for field_name in required_fields:
            if field_name not in card_data or not card_data[field_name]:
                result.add_error(ValidationError(
                    error_type=ValidationErrorType.MISSING_REQUIRED_FIELD,
                    message=f"Required field '{field_name}' is missing or empty in dataset_card",
                    field=field_name,
                ))

        # Validate privacy level
        valid_privacy_levels = ("public", "internal", "confidential")
        privacy_level = card_data.get("privacy_level", "")
        if privacy_level not in valid_privacy_levels:
            result.add_error(ValidationError(
                error_type=ValidationErrorType.INVALID_PRIVACY_LEVEL,
                message=f"Invalid privacy_level '{privacy_level}'. Must be one of: {valid_privacy_levels}",
                field="privacy_level",
            ))

        # Check for raw sessions if enabled
        if self.reject_raw_sessions:
            raw_session_indicators = self._detect_raw_sessions(dataset_path)
            if raw_session_indicators:
                result.add_error(ValidationError(
                    error_type=ValidationErrorType.RAW_SESSIONS_DETECTED,
                    message="Raw session data detected. Datasets must not contain raw conversations.",
                    severity="error",
                ))

        return result

    def _detect_raw_sessions(self, dataset_path: Path) -> list[str]:
        """Detect raw session indicators in a dataset.

        Looks for common patterns that indicate raw, unprocessed session data.

        Returns:
            List of detected raw session indicators.
        """
        indicators = []

        # Check for raw session file patterns
        patterns = [
            "raw_conversations",
            "raw_sessions",
            "provider_store",
            "conversation_dump",
            "session_log",
        ]

        if dataset_path.is_file():
            # Check file name
            for pattern in patterns:
                if pattern in dataset_path.name.lower():
                    indicators.append(f"filename: {pattern}")
        else:
            # Check directory structure
            for pattern in patterns:
                matching_files = list(dataset_path.rglob(f"*{pattern}*"))
                if matching_files:
                    indicators.append(f"path: {pattern}")

        return indicators

    def validate_with_card(
        self,
        dataset_path: Path | str,
        dataset_card: dict[str, Any] | None = None,
    ) -> ValidationResult:
        """Validate dataset with provided dataset_card data.

        Args:
            dataset_path: Path to the dataset.
            dataset_card: Optional dataset_card dict. If None, loads from file.

        Returns:
            ValidationResult with pass/fail and any errors.
        """
        result = ValidationResult(
            is_valid=True,
            dataset_path=str(dataset_path),
        )

        # If dataset_card provided, validate it directly
        if dataset_card is not None:
            required_fields = ("name", "description", "license", "privacy_level", "created_at", "source")
            for field_name in required_fields:
                if field_name not in dataset_card or not dataset_card[field_name]:
                    result.add_error(ValidationError(
                        error_type=ValidationErrorType.MISSING_REQUIRED_FIELD,
                        message=f"Required field '{field_name}' is missing or empty",
                        field=field_name,
                    ))

            privacy_level = dataset_card.get("privacy_level", "")
            if privacy_level not in ("public", "internal", "confidential"):
                result.add_error(ValidationError(
                    error_type=ValidationErrorType.INVALID_PRIVACY_LEVEL,
                    message=f"Invalid privacy_level '{privacy_level}'",
                    field="privacy_level",
                ))

            # Check for raw sessions if enabled
            if self.reject_raw_sessions:
                raw_indicators = self._detect_raw_sessions(Path(dataset_path))
                if raw_indicators:
                    result.add_error(ValidationError(
                        error_type=ValidationErrorType.RAW_SESSIONS_DETECTED,
                        message="Raw session data detected",
                    ))

            return result

        # Otherwise, load from file
        return self.validate(dataset_path)
