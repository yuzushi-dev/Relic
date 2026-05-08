"""Dataset card schema and validation for adapter training labs.

This module defines the required dataset_card format for any dataset
used in adapter training. It ensures reproducibility and privacy compliance.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class DatasetCardSchema:
    """Schema version for dataset cards."""

    version: str = "1.0"
    required_fields: tuple[str, ...] = (
        "name",
        "description",
        "license",
        "privacy_level",
        "created_at",
        "source",
    )


@dataclass
class DatasetCard:
    """Dataset card containing metadata for adapter training datasets.

    A dataset_card is REQUIRED for every dataset used in adapter training.
    This ensures reproducibility, privacy compliance, and proper documentation.

    Attributes:
        name: Unique identifier for the dataset.
        description: Human-readable description of the dataset.
        license: License under which the dataset is available.
        privacy_level: Privacy classification (public, internal, confidential).
        created_at: ISO timestamp of dataset creation.
        source: Origin of the dataset (e.g., collection method, existing dataset).
        version: Dataset version for reproducibility.
        splits: Available data splits (train, eval, test).
        schema_hash: Hash of the data schema for validation.
        citations: Academic citations if applicable.
        limitations: Known limitations or biases.
    """

    name: str
    description: str
    license: str
    privacy_level: str
    created_at: str
    source: str
    version: str = "1.0"
    splits: dict[str, int] = field(default_factory=dict)
    schema_hash: str = ""
    citations: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate required fields."""
        if not self.name:
            raise ValueError("dataset_card is invalid: requires non-empty name")
        if not self.description:
            raise ValueError("dataset_card is invalid: requires non-empty description")
        if self.privacy_level not in ("public", "internal", "confidential"):
            raise ValueError(
                f"dataset_card is invalid: privacy_level must be 'public', 'internal', or 'confidential', "
                f"got '{self.privacy_level}'"
            )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "description": self.description,
            "license": self.license,
            "privacy_level": self.privacy_level,
            "created_at": self.created_at,
            "source": self.source,
            "version": self.version,
            "splits": self.splits,
            "schema_hash": self.schema_hash,
            "citations": self.citations,
            "limitations": self.limitations,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DatasetCard:
        """Create DatasetCard from dictionary."""
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            license=data.get("license", ""),
            privacy_level=data.get("privacy_level", "internal"),
            created_at=data.get("created_at", ""),
            source=data.get("source", ""),
            version=data.get("version", "1.0"),
            splits=data.get("splits", {}),
            schema_hash=data.get("schema_hash", ""),
            citations=data.get("citations", []),
            limitations=data.get("limitations", []),
            tags=data.get("tags", []),
        )

    @classmethod
    def from_json_file(cls, path: Path | str) -> DatasetCard:
        """Load dataset card from JSON file."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Dataset card not found: {path}")
        with open(path) as f:
            data = json.load(f)
        return cls.from_dict(data)

    def to_json_file(self, path: Path | str) -> None:
        """Save dataset card to JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    def compute_schema_hash(self) -> str:
        """Compute hash of the dataset schema for validation."""
        schema_data = {
            "name": self.name,
            "description": self.description,
            "license": self.license,
            "privacy_level": self.privacy_level,
            "version": self.version,
        }
        schema_str = json.dumps(schema_data, sort_keys=True)
        return hashlib.sha256(schema_str.encode()).hexdigest()[:16]

    def is_valid(self) -> bool:
        """Check if dataset card has all required fields."""
        schema = DatasetCardSchema()
        data = self.to_dict()
        for field_name in schema.required_fields:
            if not data.get(field_name):
                return False
        return True


def require_dataset_card(func):
    """Decorator that enforces dataset_card presence.

    Use this decorator on functions that require a dataset_card
    to ensure proper validation before proceeding.
    """
    def wrapper(*args, **kwargs):
        # Extract dataset_card from kwargs or args
        dataset_card = kwargs.get("dataset_card")
        if dataset_card is None:
            for arg in args:
                if isinstance(arg, DatasetCard):
                    dataset_card = arg
                    break

        if dataset_card is None:
            raise ValueError(
                "dataset_card is required. Provide a DatasetCard instance "
                "to validate your dataset before training."
            )

        if not isinstance(dataset_card, DatasetCard):
            raise TypeError(
                f"dataset_card must be a DatasetCard instance, got {type(dataset_card)}"
            )

        if not dataset_card.is_valid():
            raise ValueError(
                f"dataset_card is invalid. Missing required fields. "
                f"Card: {dataset_card.to_dict()}"
            )

        return func(*args, **kwargs)

    return wrapper
