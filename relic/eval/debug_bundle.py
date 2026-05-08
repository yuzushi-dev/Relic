"""Debug bundle emitter for Relic E2E.

This module creates debug bundles with redacted replays and optional
synthetic replays. All private text is redacted before inclusion.

IMPORTANT: This module must NOT export raw prompt/session text or
sealed local replay into public artifacts.
"""

import json
import random
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class RedactedEntry:
    """Redacted debug entry - all private text replaced with placeholders."""

    entry_id: str
    timestamp: str
    entry_type: str  # "prompt", "response", "correction", "memory_update"
    redacted_content: str  # Content with privacy redaction applied
    placeholder_map: dict[str, str] = field(
        default_factory=dict
    )  # Maps placeholder to original type
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "timestamp": self.timestamp,
            "entry_type": self.entry_type,
            "redacted_content": self.redacted_content,
            "placeholder_map": self.placeholder_map,
            "metadata": self.metadata,
        }


@dataclass
class SyntheticEntry:
    """Synthetic debug entry - generated without real private data."""

    entry_id: str
    timestamp: str
    entry_type: str
    synthetic_content: str
    generation_seed: int
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "timestamp": self.timestamp,
            "entry_type": self.entry_type,
            "synthetic_content": self.synthetic_content,
            "generation_seed": self.generation_seed,
            "metadata": self.metadata,
        }


@dataclass
class DebugBundle:
    """Debug bundle containing redacted and synthetic replays."""

    bundle_id: str
    created_at: str
    redacted_replay: list[RedactedEntry] = field(default_factory=list)
    synthetic_replay: list[SyntheticEntry] | None = None  # Optional synthetic replay
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        result = {
            "bundle_id": self.bundle_id,
            "created_at": self.created_at,
            "redacted_replay": [e.to_dict() for e in self.redacted_replay],
            "metadata": self.metadata,
        }
        if self.synthetic_replay:
            result["synthetic_replay"] = [e.to_dict() for e in self.synthetic_replay]
        return result

    def to_json(self, output_path: Path | str | None = None) -> str:
        """Export bundle as JSON."""
        json_str = json.dumps(self.to_dict(), indent=2, default=str)
        if output_path:
            Path(output_path).write_text(json_str)
        return json_str


# Privacy redaction patterns
PRIVACY_PATTERNS = {
    "email": r"[\w.-]+@[\w.-]+\.\w+",
    "phone": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "credit_card": r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",
    "address": r"\b\d+\s+[\w\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd)\b",
    "name": r"\b(?:Mr\.|Mrs\.|Ms\.|Dr\.|Prof\.)\s+[\w]+\b",
}


class PrivacyRedactor:
    """Redacts private information from text."""

    def __init__(self):
        self._placeholder_counter = 0
        self._current_placeholder_map: dict[str, str] = {}

    def redact(self, text: str) -> tuple[str, dict[str, str]]:
        """Redact private information from text.

        Returns:
            Tuple of (redacted_text, placeholder_map)
        """
        self._placeholder_counter = 0
        self._current_placeholder_map = {}

        redacted = text

        # Apply each privacy pattern
        for pattern_name, pattern_regex in PRIVACY_PATTERNS.items():
            import re

            matches = re.finditer(pattern_regex, redacted)
            for match in reversed(list(matches)):  # Reverse to preserve positions
                placeholder = f"[REDACTED_{pattern_name.upper()}_{self._placeholder_counter}]"
                self._current_placeholder_map[placeholder] = pattern_name
                start, end = match.span()
                redacted = redacted[:start] + placeholder + redacted[end:]
                self._placeholder_counter += 1

        return redacted, self._current_placeholder_map.copy()


def create_redacted_entry(
    entry_id: str,
    entry_type: str,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> RedactedEntry:
    """Create a redacted debug entry.

    IMPORTANT: This function redacts private text before storage.
    """
    redactor = PrivacyRedactor()
    redacted_content, placeholder_map = redactor.redact(content)

    return RedactedEntry(
        entry_id=entry_id,
        timestamp=datetime.utcnow().isoformat() + "Z",
        entry_type=entry_type,
        redacted_content=redacted_content,
        placeholder_map=placeholder_map,
        metadata=metadata or {},
    )


SYNTHETIC_TEMPLATES = {
    "prompt": [
        "[SYNTHETIC] User asked about {topic}",
        "[SYNTHETIC] Query regarding {topic}",
        "[SYNTHETIC] Request: {topic}",
    ],
    "response": [
        "[SYNTHETIC] Response addressing {topic}",
        "[SYNTHETIC] Generated answer for {topic}",
        "[SYNTHETIC] Completion of {topic}",
    ],
    "correction": [
        "[SYNTHETIC] Correction applied to {topic}",
        "[SYNTHETIC] Update for {topic}",
    ],
    "memory_update": [
        "[SYNTHETIC] Memory updated: {topic}",
        "[SYNTHETIC] New fact stored about {topic}",
    ],
}


SYNTHETIC_TOPICS = [
    "weather",
    "preferences",
    "schedule",
    "contacts",
    "tasks",
    "reminders",
    "appointments",
    "conversations",
    "projects",
    "notes",
]


def create_synthetic_entry(
    entry_id: str,
    entry_type: str,
    seed: int | None = None,
) -> SyntheticEntry:
    """Create a synthetic debug entry without real private data.

    This generates fake entries for testing/debugging without
    exposing any real private information.
    """
    if seed is None:
        seed = random.randint(0, 2**32 - 1)

    random.seed(seed)

    template_category = entry_type if entry_type in SYNTHETIC_TEMPLATES else "prompt"
    template = random.choice(SYNTHETIC_TEMPLATES[template_category])
    topic = random.choice(SYNTHETIC_TOPICS)

    synthetic_content = template.format(topic=topic)

    random.seed()  # Reset seed

    return SyntheticEntry(
        entry_id=entry_id,
        timestamp=datetime.utcnow().isoformat() + "Z",
        entry_type=entry_type,
        synthetic_content=synthetic_content,
        generation_seed=seed,
        metadata={"synthetic": True},
    )


def emit_debug_bundle(
    entries: list[dict[str, str]] | None = None,
    include_synthetic: bool = False,
    bundle_id: str | None = None,
    output_path: Path | str | None = None,
) -> DebugBundle:
    """Emit a debug bundle with redacted and optional synthetic replays.

    IMPORTANT: This function ensures no raw private text is exported.

    Args:
        entries: List of entries to redact (each with 'content' and 'type' keys)
        include_synthetic: Whether to include synthetic replay
        bundle_id: Optional bundle identifier
        output_path: Optional path to save bundle JSON

    Returns:
        DebugBundle instance
    """
    if bundle_id is None:
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        bundle_id = f"debug_bundle_{timestamp}"

    now = datetime.utcnow().isoformat() + "Z"

    redacted_replay = []
    if entries:
        for i, entry in enumerate(entries):
            redacted = create_redacted_entry(
                entry_id=f"redacted_{i}",
                entry_type=entry.get("type", "unknown"),
                content=entry.get("content", ""),
                metadata=entry.get("metadata", {}),
            )
            redacted_replay.append(redacted)

    synthetic_replay = None
    if include_synthetic:
        synthetic_replay = []
        for i in range(min(10, len(entries) if entries else 5)):
            synthetic = create_synthetic_entry(
                entry_id=f"synthetic_{i}",
                entry_type=["prompt", "response", "correction", "memory_update"][i % 4],
            )
            synthetic_replay.append(synthetic)

    bundle = DebugBundle(
        bundle_id=bundle_id,
        created_at=now,
        redacted_replay=redacted_replay,
        synthetic_replay=synthetic_replay,
    )

    if output_path:
        bundle.to_json(output_path)

    return bundle
