"""Schema validation for PromptContextPack."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from jsonschema import ValidationError, validate

if TYPE_CHECKING:
    from relic.context_pack.types import PromptContextPack

SCHEMA_PATH = Path(__file__).parent.parent.parent / "schemas" / "prompt_context_pack.schema.json"

# Cache the loaded schema
_SCHEMA_CACHE: dict[str, Any] | None = None


def _load_schema() -> dict[str, Any]:
    """Load JSON schema from file."""
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is None:
        if not SCHEMA_PATH.exists():
            raise FileNotFoundError(f"Schema not found at {SCHEMA_PATH}")
        with open(SCHEMA_PATH) as f:
            _SCHEMA_CACHE = json.load(f)
    return _SCHEMA_CACHE


def validate_pack(pack: dict[str, Any] | "PromptContextPack") -> list[str]:
    """Validate a pack against the JSON schema.

    Args:
        pack: Either a dict or a PromptContextPack instance.

    Returns:
        List of validation error messages. Empty list means valid.

    Raises:
        FileNotFoundError: If schema file not found.
    """
    schema = _load_schema()

    # Convert PromptContextPack to dict if needed
    if hasattr(pack, "to_dict"):
        data = pack.to_dict()
    else:
        data = pack

    errors: list[str] = []
    try:
        validate(instance=data, schema=schema)
    except ValidationError as e:
        errors.append(f"Validation error: {e.message}")
        # Collect all error details
        if e.context:
            for sub_error in e.context:
                errors.append(f"  At {' -> '.join(str(p) for p in sub_error.path)}: {sub_error.message}")
    except Exception as e:
        errors.append(f"Unexpected validation error: {e}")

    return errors


def validate_subject_scope(pack: dict[str, Any] | "PromptContextPack") -> list[str]:
    """Validate that the pack has subject scope defined.

    Args:
        pack: Either a dict or a PromptContextPack instance.

    Returns:
        List of validation error messages. Empty means valid.
    """
    errors: list[str] = []

    # Convert PromptContextPack to dict if needed
    if hasattr(pack, "to_dict"):
        data = pack.to_dict()
    else:
        data = pack

    # Check if at least one system source, continuity item, memory candidate,
    # or knowledge candidate has scope defined
    has_scope = False

    for source in data.get("system_sources", []):
        if source.get("scope"):
            has_scope = True
            break

    if not has_scope:
        for item in data.get("continuity_items", []):
            if item.get("scope"):
                has_scope = True
                break

    if not has_scope:
        for candidate in data.get("memory_candidates", []):
            if candidate.get("scope"):
                has_scope = True
                break

    if not has_scope:
        for candidate in data.get("knowledge_candidates", []):
            if candidate.get("scope"):
                has_scope = True
                break

    if not has_scope:
        errors.append(
            "Pack must have at least one subject scope defined in "
            "system_sources, continuity_items, memory_candidates, or knowledge_candidates"
        )

    return errors
