"""Chronicle snapshot capture module, T020.

Module: relic.chronicle.snapshots
Version: chronicle-snapshots/v1

Provides high-level snapshot capture with automatic:
- content_hash via compute_checksum (mandatory, no inline hashlib)
- large content offloading to filesystem (~/.relic/chronicle/snapshots/{id}.blob)
- diff computation from previous snapshot when previous_snapshot_id provided
- emit_snapshot() call for dual-write persistence

Reference: docs/chronicle/agentic-development-plan.md §8.1, T014
"""
from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any
from uuid import UUID

from relic.artifacts.checksums import compute_checksum
from relic.chronicle.emitter import emit_snapshot
from relic.chronicle.enums import RetentionPolicy
from relic.persistence import PrivacyLevel

logger = logging.getLogger(__name__)

# Threshold for large content offloading (1 MB)
LARGE_CONTENT_THRESHOLD = 1024 * 1024


def _snapshots_dir() -> Path:
    """Return ~/.relic/chronicle/snapshots/, creating if needed."""
    d = Path.home() / ".relic" / "chronicle" / "snapshots"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load_previous_snapshot(snapshot_id: UUID) -> dict[str, Any] | str | None:
    """Load previous snapshot content from filesystem if stored as blob."""
    blob_path = _snapshots_dir() / f"{snapshot_id}.blob"
    if blob_path.exists():
        try:
            with open(blob_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"[snapshots] Failed to load previous snapshot {snapshot_id}: {e}")
    return None


def _compute_diff(
    previous_content: dict[str, Any] | str,
    current_content: dict[str, Any] | str,
) -> dict[str, Any]:
    """Compute diff between previous and current content.
    
    Returns dict with added/removed/changed keys.
    """
    diff: dict[str, Any] = {"added": [], "removed": [], "changed": []}
    
    # Normalize to dict for comparison
    if isinstance(previous_content, str):
        prev_dict: dict[str, Any] = {"_raw": previous_content}
    else:
        prev_dict = previous_content
        
    if isinstance(current_content, str):
        curr_dict: dict[str, Any] = {"_raw": current_content}
    else:
        curr_dict = current_content
    
    prev_keys = set(prev_dict.keys())
    curr_keys = set(curr_dict.keys())
    
    # Added keys
    diff["added"] = sorted(list(curr_keys - prev_keys))
    
    # Removed keys
    diff["removed"] = sorted(list(prev_keys - curr_keys))
    
    # Changed keys (present in both but different values)
    common = prev_keys & curr_keys
    for key in common:
        prev_val = prev_dict[key]
        curr_val = curr_dict[key]
        if isinstance(prev_val, dict) and isinstance(curr_val, dict):
            if prev_val != curr_val:
                diff["changed"].append(key)
        elif prev_val != curr_val:
            diff["changed"].append(key)
    
    return diff


def _serialize_content(content: dict[str, Any] | str | bytes) -> tuple[str, int]:
    """Serialize content to string and return (serialized, size_bytes).
    
    For dict/list: JSON dumps
    For str: UTF-8 encoded
    For bytes: decoded to str
    """
    if isinstance(content, dict):
        serialized = json.dumps(content, sort_keys=True, separators=(",", ":"))
        return serialized, len(serialized.encode("utf-8"))
    elif isinstance(content, list):
        serialized = json.dumps(content, sort_keys=True, separators=(",", ":"))
        return serialized, len(serialized.encode("utf-8"))
    elif isinstance(content, str):
        return content, len(content.encode("utf-8"))
    else:
        # bytes - decode to str
        decoded = content.decode("utf-8", errors="replace")
        return decoded, len(decoded.encode("utf-8"))


def _store_large_content(snapshot_id: UUID, content: dict[str, Any] | str | bytes) -> str:
    """Store large content to filesystem, return content_ref path."""
    blob_path = _snapshots_dir() / f"{snapshot_id}.blob"
    
    if isinstance(content, bytes):
        with open(blob_path, "wb") as f:
            f.write(content)
    elif isinstance(content, dict):
        with open(blob_path, "w", encoding="utf-8") as f:
            json.dump(content, f, sort_keys=True)
    else:
        with open(blob_path, "w", encoding="utf-8") as f:
            f.write(str(content) if not isinstance(content, str) else content)
    
    return str(blob_path)


def capture_snapshot(
    *,
    snapshot_type: str,
    scope_ref: str,
    content: dict[str, Any] | str | bytes,
    subject_id: str | None = None,
    trigger_event_id: UUID | None = None,
    previous_snapshot_id: UUID | None = None,
    sensitivity: PrivacyLevel = PrivacyLevel.SAFE,
    retention_policy: RetentionPolicy = RetentionPolicy.STANDARD_365D,
    trace_id: UUID | None = None,
) -> UUID:
    """Capture a state snapshot with automatic hash, storage, and diff.

    Args:
        snapshot_type: Type identifier (e.g., "profile_snapshot", "memory_state")
        scope_ref: Reference scope (e.g., "session:uuid", "profile:uuid")
        content: The snapshot content (dict, str, or bytes)
        subject_id: Optional subject identifier
        trigger_event_id: Optional event that triggered this snapshot
        previous_snapshot_id: Optional previous snapshot for diff computation
        sensitivity: Privacy level (default: SAFE)
        retention_policy: Retention policy (default: STANDARD_365D)
        trace_id: Optional trace ID for correlation

    Returns:
        snapshot_id: UUID of the created snapshot

    Raises:
        ValueError: If snapshot_type or scope_ref is empty/whitespace
    """
    # Validation
    if not snapshot_type or not snapshot_type.strip():
        raise ValueError("snapshot_type cannot be empty")
    if not scope_ref or not scope_ref.strip():
        raise ValueError("scope_ref cannot be empty")
    
    # Normalize enum values
    if isinstance(sensitivity, str):
        try:
            sensitivity = PrivacyLevel(sensitivity)
        except ValueError:
            sensitivity = PrivacyLevel.SAFE
    
    if isinstance(retention_policy, str):
        try:
            retention_policy = RetentionPolicy(retention_policy)
        except ValueError:
            retention_policy = RetentionPolicy.STANDARD_365D
    
    # Serialize content to check size
    serialized, size_bytes = _serialize_content(content)
    
    # Determine storage strategy
    temp_id: UUID | None = None
    content_ref: str | None = None
    
    # Large content (>1MB): store blob in filesystem before emit
    if size_bytes > LARGE_CONTENT_THRESHOLD:
        temp_id = uuid.uuid4()
        _store_large_content(temp_id, content)
        # content_ref will be updated after we get actual snapshot_id
        logger.debug(f"[snapshots] Large content ({size_bytes} bytes) stored with temp_id {temp_id}")
    
    # Compute content hash via compute_checksum (OBBLIGATORIO)
    if isinstance(content, dict):
        content_hash_hex = compute_checksum(content)
    elif isinstance(content, list):
        content_hash_hex = compute_checksum(content)
    elif isinstance(content, str):
        content_hash_hex = compute_checksum(content)
    else:
        # bytes: decode to string for checksum
        content_hash_hex = compute_checksum(content.decode("utf-8", errors="replace"))
    
    content_hash = f"sha256:{content_hash_hex}"
    
    # Small content: inline reference
    if size_bytes <= LARGE_CONTENT_THRESHOLD:
        content_ref = f"inline:{size_bytes}b"
    
    # Diff from previous snapshot if provided
    diff_from_previous: dict[str, Any] | None = None
    if previous_snapshot_id is not None:
        prev_content = _load_previous_snapshot(previous_snapshot_id)
        if prev_content is not None:
            diff_from_previous = _compute_diff(prev_content, serialized)
    
    # Call emit_snapshot (T014)
    # Pass content_ref even for large content (will be corrected after rename)
    if temp_id is not None:
        actual_blob_path = _snapshots_dir() / f"{temp_id}.blob"
        content_ref = str(actual_blob_path)
    
    snapshot_id = emit_snapshot(
        snapshot_type=snapshot_type,
        subject_id=subject_id,
        scope_ref=scope_ref,
        content=content,
        trigger_event_id=trigger_event_id,
        previous_snapshot_id=previous_snapshot_id,
        sensitivity=sensitivity,
        retention_policy=retention_policy,
        trace_id=trace_id,
        content_ref=content_ref,
        diff_from_previous=diff_from_previous,
    )
    
    # If we stored large content with temp_id, rename blob with actual snapshot_id
    if temp_id is not None:
        temp_blob = _snapshots_dir() / f"{temp_id}.blob"
        actual_blob = _snapshots_dir() / f"{snapshot_id}.blob"
        if temp_blob.exists() and not actual_blob.exists():
            temp_blob.rename(actual_blob)
    
    return snapshot_id
