"""PromptContextPack (PCP) — typed, schema-validated, redacted, traceable per-turn contract.

CAC becomes the ONLY path by which memory candidates are admitted
into injected runtime context.
"""

from __future__ import annotations

# Core types from types module
from relic.context_pack.types import (
    PromptContextPack,
    SystemSource,
    MemoryCandidate,
    KnowledgeCandidate,
    ContinuityItem,
    BlockedItem,
    SubjectScope,
    # Enums
    TaskType,
    RoleplayLevel,
    ContinuityMode,
    DisclosureLevel,
    ContextSource,
)

# Schema validation
from relic.context_pack.schema import (
    validate_pack,
    validate_subject_scope,
    SCHEMA_PATH,
)

# Renderer
from relic.context_pack.render import (
    render_compact,
    render_with_sources,
    check_no_raw_prompt,
    get_blocked_ids,
    is_item_blocked,
)

# Trace
from relic.context_pack.trace import (
    PCPTrace,
    PCPTraceEntry,
    PCPTraceEvent,
)

# CAC Adapter
from relic.context_pack.adapters.cac import CACContextPackAdapter, CACContextPackAdapterResult

# Builder
from relic.context_pack.builder import ContextPackBuilder, create_context_pack_from_cac

__all__ = [
    # Core types
    "PromptContextPack",
    "SystemSource",
    "MemoryCandidate",
    "KnowledgeCandidate",
    "ContinuityItem",
    "BlockedItem",
    "SubjectScope",
    # Enums
    "TaskType",
    "RoleplayLevel",
    "ContinuityMode",
    "DisclosureLevel",
    "ContextSource",
    # Schema
    "validate_pack",
    "validate_subject_scope",
    "SCHEMA_PATH",
    # Renderer
    "render_compact",
    "render_with_sources",
    "check_no_raw_prompt",
    "get_blocked_ids",
    "is_item_blocked",
    # Trace
    "PCPTrace",
    "PCPTraceEntry",
    "PCPTraceEvent",
    # CAC Adapter
    "CACContextPackAdapter",
    "CACContextPackAdapterResult",
    # Builder
    "ContextPackBuilder",
    "create_context_pack_from_cac",
]
