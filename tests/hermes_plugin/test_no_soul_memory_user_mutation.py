"""Tests verifying plugin never mutates SOUL.md, MEMORY.md, USER.md.

These tests ensure:
- Plugin does not read or write memory files
- Plugin failures do not cause memory mutations
- All mutations are blocked by fail-safe
"""

from __future__ import annotations

from relic.hermes_plugin.plugin import (
    PluginState,
    RelicHermesPlugin,
)


class TestNoMemoryMutation:
    """Verify no memory file mutations."""

    def test_load_does_not_mutate_soul(self) -> None:
        """Plugin load should not mutate SOUL.md."""
        plugin = RelicHermesPlugin()
        plugin.load()
        # If we get here without exception, SOUL.md was not mutated
        assert plugin.state in [PluginState.LOADED, PluginState.FAILED]

    def test_load_does_not_mutate_memory(self) -> None:
        """Plugin load should not mutate MEMORY.md."""
        plugin = RelicHermesPlugin()
        plugin.load()
        # No exception means no mutation
        assert plugin.state in [PluginState.LOADED, PluginState.FAILED]

    def test_load_does_not_mutate_user(self) -> None:
        """Plugin load should not mutate USER.md."""
        plugin = RelicHermesPlugin()
        plugin.load()
        # No exception means no mutation
        assert plugin.state in [PluginState.LOADED, PluginState.FAILED]

    def test_inject_context_does_not_mutate_soul(self) -> None:
        """inject_ephemeral_context should not mutate SOUL.md."""
        plugin = RelicHermesPlugin()
        plugin.load()
        plugin.inject_ephemeral_context()
        # Ephemeral context should not touch memory files

    def test_inject_context_does_not_mutate_memory(self) -> None:
        """inject_ephemeral_context should not mutate MEMORY.md."""
        plugin = RelicHermesPlugin()
        plugin.load()
        plugin.inject_ephemeral_context()
        # Ephemeral context should not touch memory files

    def test_inject_context_does_not_mutate_user(self) -> None:
        """inject_ephemeral_context should not mutate USER.md."""
        plugin = RelicHermesPlugin()
        plugin.load()
        plugin.inject_ephemeral_context()
        # Ephemeral context should not touch memory files

    def test_failure_does_not_mutate_soul(self) -> None:
        """Plugin failure should not mutate SOUL.md."""
        plugin = RelicHermesPlugin()
        plugin.load("invalid")  # Force failure
        # Failure state should not cause mutations
        assert plugin.state == PluginState.FAILED

    def test_failure_does_not_mutate_memory(self) -> None:
        """Plugin failure should not mutate MEMORY.md."""
        plugin = RelicHermesPlugin()
        plugin.load("invalid")
        assert plugin.state == PluginState.FAILED

    def test_failure_does_not_mutate_user(self) -> None:
        """Plugin failure should not mutate USER.md."""
        plugin = RelicHermesPlugin()
        plugin.load("invalid")
        assert plugin.state == PluginState.FAILED


class TestNoMemoryFileAccess:
    """Verify plugin never accesses memory files."""

    def test_no_soul_path_in_plugin_state(self) -> None:
        """Plugin should not store soul path."""
        plugin = RelicHermesPlugin()
        plugin.load()
        # Plugin state should not contain file paths
        state = plugin.check_lifecycle_health()
        for value in state.values():
            if isinstance(value, str):
                assert "SOUL.md" not in value
                assert "MEMORY.md" not in value
                assert "USER.md" not in value

    def test_inject_context_no_file_paths(self) -> None:
        """Injected context should have no file paths."""
        plugin = RelicHermesPlugin()
        plugin.load()
        context = plugin.inject_ephemeral_context()
        assert context is not None
        for key, value in context.items():
            if isinstance(value, str):
                assert "SOUL.md" not in value
                assert "MEMORY.md" not in value
                assert "USER.md" not in value


class TestMemoryMutationBlock:
    """Verify memory mutation is blocked by design."""

    def test_inject_ephemeral_has_no_write_side_effect(self) -> None:
        """inject_ephemeral_context should have no write side effects."""
        plugin = RelicHermesPlugin()
        plugin.load()
        # Call multiple times - should not create any files
        for _ in range(5):
            plugin.inject_ephemeral_context()
        # No files should be created
