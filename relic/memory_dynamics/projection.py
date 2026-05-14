"""Human-readable memory projections with redaction.

This module implements human-readable projections of memory state
that maintain privacy through redaction.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


# Privacy patterns for redaction
PRIVACY_PATTERNS = [
    (r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}', '[REDACTED_EMAIL]'),
    (r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b', '[REDACTED_PHONE]'),
    (r'\b\d{3}-\d{2}-\d{4}\b', '[REDACTED_SSN]'),
    (r'sk_live_[a-zA-Z0-9]+', '[REDACTED_API_KEY]'),
    (r'sk_test_[a-zA-Z0-9]+', '[REDACTED_API_KEY]'),
    (r'(?:password|passwd|pwd)[:\s]*[^\s]+', '[REDACTED_PASSWORD]'),
    (r'(?:credit\s*card|card\s*number)[:\s]*\d+[^\s]*', '[REDACTED_CARD]'),
]


@dataclass
class RedactedProjection:
    """A redacted human-readable memory projection."""
    memory_id: str
    content_hash: str
    redacted_content: str
    redacted_fields: list[str] = field(default_factory=list)
    privacy_level: str = "SAFE"
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "content_hash": self.content_hash,
            "redacted_content": self.redacted_content,
            "redacted_fields": self.redacted_fields,
            "privacy_level": self.privacy_level,
            "created_at": self.created_at.isoformat(),
        }


class ProjectionGenerator:
    """Generator for human-readable memory projections with redaction."""
    
    def __init__(self):
        self._projections: dict[str, RedactedProjection] = {}
    
    def redact_content(self, content: str) -> tuple[str, list[str]]:
        """Redact sensitive patterns from content.
        
        Returns:
            Tuple of (redacted_content, list_of_redacted_patterns)
        """
        redacted = content
        redacted_fields: list[str] = []
        
        for pattern, replacement in PRIVACY_PATTERNS:
            matches = re.findall(pattern, redacted, re.IGNORECASE)
            if matches:
                redacted_fields.extend([m for m in matches if m not in redacted_fields])
                redacted = re.sub(pattern, replacement, redacted, flags=re.IGNORECASE)
        
        return redacted, redacted_fields
    
    def generate_projection(
        self,
        memory_id: str,
        content: str,
        privacy_level: str = "SAFE",
    ) -> RedactedProjection:
        """Generate a redacted human-readable projection for a memory.
        
        The projection contains only hashes and redacted content,
        never raw sensitive data.
        """
        redacted_content, redacted_fields = self.redact_content(content)
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        
        projection = RedactedProjection(
            memory_id=memory_id,
            content_hash=content_hash,
            redacted_content=redacted_content,
            redacted_fields=redacted_fields,
            privacy_level=privacy_level,
        )
        
        self._projections[memory_id] = projection
        return projection
    
    def get_projection(self, memory_id: str) -> RedactedProjection | None:
        """Get a projection by memory ID."""
        return self._projections.get(memory_id)
    
    def generate_summary(
        self,
        memory_ids: list[str],
        memory_content_map: dict[str, str],
    ) -> str:
        """Generate a human-readable summary of multiple memories.
        
        All sensitive content is redacted.
        """
        summaries = []
        
        for mem_id in memory_ids:
            content = memory_content_map.get(mem_id, "")
            projection = self.generate_projection(mem_id, content)
            summaries.append(f"- {projection.redacted_content}")
        
        return "\n".join(summaries) if summaries else "No memories to summarize."
    
    def verify_no_raw_sensitive(
        self,
        output: str,
    ) -> bool:
        """Verify output contains no raw sensitive text.
        
        Returns True if all privacy patterns are redacted.
        """
        for pattern, _ in PRIVACY_PATTERNS:
            if re.search(pattern, output, re.IGNORECASE):
                return False
        return True
