"""Compact renderer for PromptContextPack with redaction and blocked item handling."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from relic.context_pack.types import PromptContextPack

from relic.context_pack.types import DisclosureLevel


# Markers that indicate raw content should not be injected
_RAW_MARKERS = ["[RAW_PROMPT]", "[RAW_USER]", "[PRIVATE]", "[SENSITIVE]"]


def render_compact(pack: "PromptContextPack") -> str:
    """Render a compact text representation of the pack.

    This renders only the summary-level content, never raw prompts.
    Blocked items are explicitly excluded.

    Args:
        pack: The PromptContextPack to render.

    Returns:
        Compact text representation suitable for context injection.
    """
    lines = [
        f"=== Context Pack {pack.pack_id} ===",
        f"Task: {pack.task_type.value} | Roleplay: {pack.roleplay_level.value}",
        f"Continuity: {pack.continuity_mode.value} | Disclosure: {pack.disclosure_required}",
    ]

    # System sources with content
    for source in pack.system_sources:
        if source.injected and source.content:
            # Check if all scope items allow disclosure
            can_disclose = _can_disclose(source.scope)
            if can_disclose:
                lines.append(f"\n[{source.source.value}] (priority={source.priority})")
                lines.append(source.content)

    # Continuity items
    if pack.continuity_items:
        lines.append("\n--- Continuity ---")
        for item in pack.continuity_items:
            if _can_disclose(item.scope):
                lines.append(f"  [{item.item_type}] {item.summary}")

    # Memory candidates
    if pack.memory_candidates:
        lines.append("\n--- Memory Candidates ---")
        for candidate in pack.memory_candidates:
            if _can_disclose(candidate.scope):
                lines.append(f"  [{candidate.memory_type}] {candidate.summary} (relevance={candidate.relevance_score:.2f})")

    # Knowledge candidates
    if pack.knowledge_candidates:
        lines.append("\n--- Knowledge Candidates ---")
        for candidate in pack.knowledge_candidates:
            if _can_disclose(candidate.scope):
                lines.append(f"  [{candidate.knowledge_type}] {candidate.content[:200]}...")

    # Blocked items count (never injected)
    if pack.blocked_items:
        lines.append(f"\n--- Blocked Items: {len(pack.blocked_items)} (excluded) ---")

    return "\n".join(lines)


def render_with_sources(pack: "PromptContextPack", source_names: list[str] | None = None) -> str:
    """Render pack with specific source filtering.

    Args:
        pack: The PromptContextPack to render.
        source_names: Optional list of source names to include. If None, includes all.

    Returns:
        Text representation with source filtering.
    """
    lines = [
        f"=== Context Pack {pack.pack_id} ===",
        f"Task: {pack.task_type.value} | Mode: {pack.continuity_mode.value}",
    ]

    # Filter system sources
    sources_to_include = {name for name in source_names} if source_names else None

    for source in pack.system_sources:
        if source.injected and source.content:
            if sources_to_include is None or source.source.value in sources_to_include:
                if _can_disclose(source.scope):
                    lines.append(f"\n[{source.source.value}]")
                    lines.append(source.content)

    return "\n".join(lines)


def _can_disclose(scope: list) -> bool:
    """Check if scope allows disclosure.

    Args:
        scope: List of SubjectScope objects or dicts.

    Returns:
        True if any scope allows disclosure (not PRIVATE).
    """
    if not scope:
        return True  # No scope means open by default

    for s in scope:
        if hasattr(s, "disclosure_level"):
            if s.disclosure_level != DisclosureLevel.PRIVATE:
                return True
        elif isinstance(s, dict):
            if s.get("disclosure_level") != "private":
                return True

    return False


def check_no_raw_prompt(pack: "PromptContextPack") -> bool:
    """Check that pack contains no raw prompt markers.

    Raw prompt markers like "[RAW_PROMPT]" or user private fact patterns
    should fail validation.

    Args:
        pack: The PromptContextPack to check.

    Returns:
        True if no raw prompt markers detected.
    """
    for source in pack.system_sources:
        if source.content:
            for marker in _RAW_MARKERS:
                if marker in source.content:
                    return False

    for candidate in pack.memory_candidates:
        for marker in _RAW_MARKERS:
            if marker in candidate.summary:
                return False

    return True


def get_blocked_ids(pack: "PromptContextPack") -> set[str]:
    """Get the set of blocked item IDs.

    Args:
        pack: The PromptContextPack to check.

    Returns:
        Set of blocked item IDs.
    """
    return {item.item_id for item in pack.blocked_items}


def is_item_blocked(item_id: str, pack: "PromptContextPack") -> bool:
    """Check if an item is blocked.

    Args:
        item_id: The item ID to check.
        pack: The PromptContextPack to check.

    Returns:
        True if the item is blocked.
    """
    return item_id in get_blocked_ids(pack)
