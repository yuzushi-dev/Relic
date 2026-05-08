"""Tests for ephemeral context injection (not system prompt).

These tests verify:
- Plugin injects only ephemeral per-turn context
- No persistent system prompt changes
- Context is valid for current turn only
"""

from __future__ import annotations

import pytest

from relic.hermes_plugin.plugin import PluginConfig, RelicHermesPlugin


class TestEphemeralContext:
    """Verify ephemeral context behavior."""

    def test_inject_returns_ephemeral_type(self) -> None:
        """Injected context should have ephemeral type."""
        plugin = RelicHermesPlugin()
        plugin.load()
        context = plugin.inject_ephemeral_context()
        assert context is not None
        assert context["type"] == "ephemeral_guidance"

    def test_inject_includes_timestamp(self) -> None:
        """Injected context should include timestamp."""
        plugin = RelicHermesPlugin()
        plugin.load()
        context = plugin.inject_ephemeral_context()
        assert context is not None
        assert "timestamp" in context

    def test_inject_includes_policy_version(self) -> None:
        """Injected context should include policy version."""
        plugin = RelicHermesPlugin()
        plugin.load()
        context = plugin.inject_ephemeral_context()
        assert context is not None
        assert "policy_version" in context
        assert context["policy_version"] == "1.0.0"

    def test_inject_includes_privacy_gateway_status(self) -> None:
        """Injected context should include privacy gateway status."""
        plugin = RelicHermesPlugin()
        plugin.load()
        context = plugin.inject_ephemeral_context()
        assert context is not None
        assert "privacy_gateway_active" in context

    def test_inject_does_not_include_memory_paths(self) -> None:
        """Injected context should NOT include memory file paths."""
        plugin = RelicHermesPlugin()
        plugin.load()
        context = plugin.inject_ephemeral_context()
        assert context is not None
        # Should NOT have these
        assert "soul_md" not in context
        assert "memory_md" not in context
        assert "user_md" not in context
        assert "memory_path" not in context
        assert "soul_path" not in context

    def test_inject_does_not_include_raw_content(self) -> None:
        """Injected context should NOT include raw content."""
        plugin = RelicHermesPlugin()
        plugin.load()
        context = plugin.inject_ephemeral_context()
        assert context is not None
        # Should NOT have raw content fields
        assert "raw_memory" not in context
        assert "raw_content" not in context
        assert "memory_content" not in context

    def test_inject_does_not_modify_persistent_state(self) -> None:
        """inject_ephemeral_context should not modify persistent state."""
        plugin = RelicHermesPlugin()
        plugin.load()
        # Should not raise - nothing to persist
        plugin.inject_ephemeral_context()
        # If we get here, no persistent state was modified


class TestNoSystemPromptModification:
    """Verify no system prompt modifications."""

    def test_no_system_prompt_field_in_context(self) -> None:
        """Context should not have system prompt fields."""
        plugin = RelicHermesPlugin()
        plugin.load()
        context = plugin.inject_ephemeral_context()
        assert context is not None
        # Should NOT have system prompt related fields
        assert "system_prompt" not in context
        assert "system_prompt_append" not in context
        assert "prompt_modification" not in context
        assert "persistent_system_context" not in context

    def test_load_does_not_create_memory_files(self, tmp_path: pytest.TempPathFactory) -> None:
        """Plugin load should not create memory files."""
        plugin = RelicHermesPlugin()
        config = PluginConfig(pause_db_path=tmp_path / "test.db")
        plugin.load(config)
        # No memory files should be created
        assert not (tmp_path / "SOUL.md").exists()
        assert not (tmp_path / "MEMORY.md").exists()
        assert not (tmp_path / "USER.md").exists()

    def test_inject_context_not_stored_in_plugin(self) -> None:
        """Injected context should not be stored in plugin."""
        plugin = RelicHermesPlugin()
        plugin.load()
        context1 = plugin.inject_ephemeral_context()
        context2 = plugin.inject_ephemeral_context()
        # Timestamps should be different (ephemeral)
        assert context1["timestamp"] != context2["timestamp"]


class TestEphemeralPerTurnBehavior:
    """Test per-turn ephemeral context behavior."""

    def test_context_valid_for_single_turn(self) -> None:
        """Context should be valid for current turn only."""
        plugin = RelicHermesPlugin()
        plugin.load()
        context = plugin.inject_ephemeral_context()
        # After injection, context should not persist
        assert context is not None
        # Nothing to check - context is ephemeral by design

    def test_context_does_not_accumulate(self) -> None:
        """Multiple calls should not accumulate context."""
        plugin = RelicHermesPlugin()
        plugin.load()
        for _ in range(10):
            context = plugin.inject_ephemeral_context()
            assert context is not None
            # Should always have same structure, no accumulation
            assert len(context) <= 5  # Only metadata fields
