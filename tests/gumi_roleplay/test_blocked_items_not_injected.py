"""Tests for PromptContextPack blocked items not injected."""

from __future__ import annotations

import pytest

from relic.context_pack import (
    PromptContextPack,
    BlockedItem,
    SystemSource,
    ContinuityItem,
    MemoryCandidate,
    TaskType,
    RoleplayLevel,
    ContinuityMode,
    ContextSource,
    SubjectScope,
    DisclosureLevel,
)
from relic.context_pack.render import (
    render_compact,
    is_item_blocked,
    get_blocked_ids,
)


class TestBlockedItemsNotInjected:
    """Test suite for blocked items being excluded from rendering."""

    def test_blocked_items_not_in_render(self, pack_with_blocked_items):
        """Test that blocked items are not included in rendered output."""
        output = render_compact(pack_with_blocked_items)

        # Blocked items should be mentioned in count but not injected
        assert "Blocked Items: 3" in output
        assert "blocked-a" not in output
        assert "blocked-b" not in output
        assert "blocked-c" not in output

    def test_blocked_items_not_in_memory_render(self):
        """Test that blocked memory candidate is not in output."""
        pack = PromptContextPack(
            pack_id="PCP-block-mem",
            session_id="SES-block-mem",
            turn_id="TURN-block-mem",
            task_type=TaskType.RELATIONAL,
            memory_candidates=[
                MemoryCandidate(
                    candidate_id="mem-1",
                    memory_type="episodic",
                    summary="Normal memory",
                    relevance_score=0.8,
                ),
            ],
            blocked_items=[
                BlockedItem(item_id="blocked-mem", reason="Contains sensitive info"),
            ],
        )
        output = render_compact(pack)

        # Blocked item should not appear in the output
        assert "blocked-mem" not in output
        # But normal memory should appear
        assert "Normal memory" in output

    def test_is_item_blocked_true(self, pack_with_blocked_items):
        """Test is_item_blocked returns True for blocked items."""
        assert is_item_blocked("blocked-a", pack_with_blocked_items) is True
        assert is_item_blocked("blocked-b", pack_with_blocked_items) is True
        assert is_item_blocked("blocked-c", pack_with_blocked_items) is True

    def test_is_item_blocked_false(self, pack_with_blocked_items):
        """Test is_item_blocked returns False for non-blocked items."""
        assert is_item_blocked("not-blocked", pack_with_blocked_items) is False

    def test_get_blocked_ids(self, pack_with_blocked_items):
        """Test get_blocked_ids returns all blocked IDs."""
        blocked = get_blocked_ids(pack_with_blocked_items)
        assert blocked == {"blocked-a", "blocked-b", "blocked-c"}

    def test_blocked_items_with_scope(self, full_pack_with_scope):
        """Test that blocked items with scope render correctly."""
        output = render_compact(full_pack_with_scope)
        # Blocked item should appear in count but not be injected
        assert "Blocked Items: 1" in output

    def test_empty_blocked_list(self, minimal_pack):
        """Test that pack with no blocked items renders correctly."""
        output = render_compact(minimal_pack)
        assert "Blocked Items:" not in output

    def test_blocked_item_with_reason_only(self):
        """Test blocked item with reason but no other fields."""
        pack = PromptContextPack(
            pack_id="PCP-block-reason",
            session_id="SES-block-reason",
            turn_id="TURN-block-reason",
            task_type=TaskType.FACTUAL,
            blocked_items=[
                BlockedItem(item_id="just-reason", reason="User opted out"),
            ],
        )
        blocked = get_blocked_ids(pack)
        assert "just-reason" in blocked

    def test_multiple_blocked_items_count(self):
        """Test rendering with many blocked items."""
        blocked_list = [
            BlockedItem(item_id=f"blocked-{i}", reason=f"Reason {i}")
            for i in range(10)
        ]
        pack = PromptContextPack(
            pack_id="PCP-many-blocked",
            session_id="SES-many-blocked",
            turn_id="TURN-many-blocked",
            task_type=TaskType.FACTUAL,
            blocked_items=blocked_list,
        )
        output = render_compact(pack)
        assert "Blocked Items: 10" in output

    def test_continuity_item_not_blocked(self, full_pack_with_scope):
        """Test that non-blocked continuity items are included."""
        output = render_compact(full_pack_with_scope)
        # ci-1 should appear in continuity section
        assert "conversation" in output
        assert "Previous conversation" in output

    def test_system_source_not_blocked(self, full_pack_with_scope):
        """Test that non-blocked system sources are included."""
        output = render_compact(full_pack_with_scope)
        # Memory source should appear
        assert "memory" in output.lower()
        assert "Memory context" in output

    def test_blocked_item_never_in_output(self, pack_with_blocked_items):
        """Comprehensive test that blocked item IDs never appear in output."""
        output = render_compact(pack_with_blocked_items)
        blocked_ids = get_blocked_ids(pack_with_blocked_items)

        for blocked_id in blocked_ids:
            assert blocked_id not in output, f"Blocked item {blocked_id} should not appear in output"
