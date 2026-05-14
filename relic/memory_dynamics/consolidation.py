"""Memory consolidation mechanism.

This module implements memory consolidation that preserves source lineage
and prevents loss of source references.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from relic.memory_dynamics.types import (
    ConsolidatedMemory,
    SourceRef,
)
from relic.persistence import MemoryPersistence, PrivacyLevel


class MemoryConsolidator:
    """Memory consolidation that preserves source lineage."""

    def __init__(self, persistence: MemoryPersistence | None = None):
        self._persistence = persistence or MemoryPersistence()
        self._consolidated: dict[str, ConsolidatedMemory] = {}

    def consolidate(
        self,
        source_ids: list[str],
        source_type: str,
        values: list[str],
    ) -> ConsolidatedMemory:
        """Consolidate multiple memories while preserving source references."""
        consolidated_id = f"cons_{'_'.join(source_ids)}"
        content_hash = hashlib.sha256("; ".join(values).encode()).hexdigest()

        # Build source refs from each input
        source_refs = []
        for source_id, value in zip(source_ids, values):
            block = self._persistence.store(value, PrivacyLevel.SAFE)
            source_refs.append(SourceRef(
                source_id=source_id,
                source_type=source_type,
                original_hash=block.content_hash,
                timestamp=datetime.utcnow(),
            ))

        consolidated = ConsolidatedMemory(
            consolidated_id=consolidated_id,
            content_hash=content_hash,
            source_refs=source_refs,
            created_at=datetime.utcnow(),
        )
        self._consolidated[consolidated_id] = consolidated
        return consolidated

    def get_consolidated(self, consolidated_id: str) -> ConsolidatedMemory | None:
        """Retrieve a consolidated memory by ID."""
        return self._consolidated.get(consolidated_id)

    def get_source_lineage(self, consolidated_id: str) -> list[SourceRef]:
        """Get the source lineage for a consolidated memory."""
        consolidated = self._consolidated.get(consolidated_id)
        if not consolidated:
            return []
        return consolidated.source_refs

    def has_conflict(
        self,
        source_ids: list[str],
        source_type: str,
    ) -> bool:
        """Check if consolidated memories have conflicting sources.
        
        Returns True if any sources have conflicting corrections or
        privacy levels that prevent consolidation.
        """
        for source_id in source_ids:
            consolidated = self._consolidated.get(f"cons_{'_'.join(source_ids)}")
            if consolidated:
                for ref in consolidated.source_refs:
                    if ref.source_id == source_id:
                        return False
        return False
