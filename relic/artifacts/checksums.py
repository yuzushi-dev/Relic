"""Checksum computation and verification for Relic artifacts.

This module provides cryptographic checksum utilities for artifact integrity
verification. All artifacts MUST have a checksum computed from their content
to ensure tamper detection.

Privacy: This module works with content hashes only - no raw content is ever
stored or transmitted.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel


class ChecksumMetadata(BaseModel):
    """Metadata for checksum verification."""

    algorithm: str = "sha256"
    computed_at: str | None = None
    field_path: str | None = None


def compute_checksum(content: dict[str, Any] | list | str) -> str:
    """Compute SHA-256 checksum of content.

    Args:
        content: Dictionary, list, or string to hash

    Returns:
        SHA-256 hex digest (64 characters)
    """
    if isinstance(content, dict):
        content_str = json.dumps(content, sort_keys=True, default=_json_serializer)
    elif isinstance(content, list):
        content_str = json.dumps(content, sort_keys=True, default=_json_serializer)
    else:
        content_str = str(content)

    return hashlib.sha256(content_str.encode("utf-8")).hexdigest()


def _json_serializer(obj: Any) -> str:
    """Custom JSON serializer for non-serializable objects."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "__str__"):
        return str(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def verify_checksum(content: dict[str, Any] | list | str, expected_checksum: str) -> bool:
    """Verify content matches expected checksum.

    Args:
        content: Content to verify
        expected_checksum: Expected SHA-256 hex digest

    Returns:
        True if checksums match, False otherwise
    """
    if len(expected_checksum) != 64:
        return False

    try:
        actual = compute_checksum(content)
        return actual == expected_checksum
    except Exception:
        return False


def compute_structural_checksum(artifact_dict: dict[str, Any]) -> str:
    """Compute checksum of artifact structure excluding mutable fields.

    This computes a checksum over the stable structure of an artifact,
    ignoring fields that change with each serialization (like timestamps).

    Args:
        artifact_dict: Artifact as dictionary

    Returns:
        SHA-256 hex digest of structure
    """
    # Fields to exclude from structural checksum (mutable)
    exclude_fields = {"id", "created_at", "updated_at", "checksum", "metadata"}

    # Filter to stable fields only
    stable_content = {
        k: v
        for k, v in artifact_dict.items()
        if k not in exclude_fields and v is not None
    }

    return compute_checksum(stable_content)


def compute_delta_checksum(original: dict[str, Any], delta: dict[str, Any]) -> str:
    """Compute checksum of delta between original and modified content.

    Useful for tracking changes to artifacts while maintaining lineage.

    Args:
        original: Original artifact content
        delta: Changes to apply

    Returns:
        SHA-256 hex digest of delta
    """
    delta_str = json.dumps(
        {"original": original, "delta": delta},
        sort_keys=True,
        default=_json_serializer,
    )
    return hashlib.sha256(delta_str.encode("utf-8")).hexdigest()


def hash_prompt(prompt_text: str) -> str:
    """Compute privacy-safe hash of prompt content.

    This allows storing references to prompts without storing the actual
    prompt content, maintaining zero-knowledge privacy guarantees.

    Args:
        prompt_text: Original prompt text

    Returns:
        SHA-256 hex digest of prompt
    """
    return hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()


def hash_hint(hint_content: str) -> str:
    """Compute privacy-safe hash of hint content.

    Args:
        hint_content: Original hint content

    Returns:
        SHA-256 hex digest of hint
    """
    return hashlib.sha256(hint_content.encode("utf-8")).hexdigest()
