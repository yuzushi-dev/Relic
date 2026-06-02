"""PR08, redacted projection for system_inferred_fields."""
from __future__ import annotations

from typing import Any

from relic.profile.inferred_fields import InferredField

RAW_TEXT_MARKERS = (
    "SECRET_RAW_PROMPT_SHOULD_NOT_APPEAR",
    "PRIVATE_HEALTH_DETAIL_SHOULD_NOT_APPEAR",
    "raw_final_prompt",
)


def project_inferred_fields(
    fields: dict[str, InferredField],
) -> dict[str, Any]:
    """Produce human-readable projection.

    Contains: field_name, value, confidence, source_count, updated_at.
    Never contains raw sensitive text. Never contains clinical terms.
    """
    projection = {}
    for name, f in fields.items():
        if f.correction_state in ("corrected", "blocked"):
            projection[name] = {
                "value": "[corrected by subject]",
                "confidence": 0.0,
                "source_count": len(f.source_refs),
                "updated_at": f.updated_at,
                "correction_state": f.correction_state,
            }
            continue

        value = f.value
        # Sanitize: never expose raw markers
        if isinstance(value, str):
            for marker in RAW_TEXT_MARKERS:
                if marker in value:
                    value = "[redacted]"
                    break

        projection[name] = {
            "value": value,
            "confidence": f.confidence,
            "source_count": len(f.source_refs),
            "updated_at": f.updated_at,
            "correction_state": f.correction_state,
        }
    return projection
