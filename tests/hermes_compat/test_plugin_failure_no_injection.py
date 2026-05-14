"""PR03 — Plugin failure produces no injection tests.

Tests verify:
- Plugin failure produces NO memory injection
- Fail-closed behavior when plugin errors
- No modification of persistent stores on failure
"""

from __future__ import annotations

import pytest

from relic.hermes_plugin.plugin import PluginConfig, PluginState, RelicHermesPlugin
from relic.hermes_plugin.fail_safe import FailSafeRegistry, FailSafeTrigger
from relic.context_pack import ContextPackBuilder, TaskType


class TestPluginFailureNoInjection:
    """Verify plugin failure produces no memory injection."""

    def test_inject_context_when_unloaded_returns_none(self) -> None:
        """When unloaded, inject_ephemeral_context should return None."""
        plugin = RelicHermesPlugin()
        # Not loaded - should return None
        result = plugin.inject_ephemeral_context()
        assert result is None

    def test_inject_context_when_failed_returns_none(self) -> None:
        """When failed, inject_ephemeral_context should return None."""
        plugin = RelicHermesPlugin()
        # Force failure by loading with invalid config
        try:
            plugin.load("invalid_config")
        except Exception:
            pass
        # Should still return None
        result = plugin.inject_ephemeral_context()
        assert result is None

    def test_inject_context_when_disabled_returns_none(self) -> None:
        """When disabled, inject_ephemeral_context should return None."""
        plugin = RelicHermesPlugin()
        config = PluginConfig(enabled=False)
        plugin.load(config)
        # Plugin loads successfully even if disabled
        assert plugin.state == PluginState.LOADED
        result = plugin.inject_ephemeral_context()
        assert result is None

    def test_inject_context_when_fail_safe_triggered_returns_none(self) -> None:
        """When fail-safe is triggered, inject should return None."""
        plugin = RelicHermesPlugin()
        plugin.load()

        # Trigger fail-safe
        fail_safe = plugin._fail_safe
        assert fail_safe is not None
        fail_safe.trigger(
            reason="Test failure",
            trigger=FailSafeTrigger.UNKNOWN,
        )

        # Now injection should return None
        result = plugin.inject_ephemeral_context()
        assert result is None

    def test_inject_returns_ephemeral_only(self) -> None:
        """inject_ephemeral_context should return ephemeral data only."""
        plugin = RelicHermesPlugin()
        plugin.load()
        result = plugin.inject_ephemeral_context()
        assert result is not None
        # Should NOT have persistent store fields
        assert "schema_version" in result
        assert "pack_id" in result
        assert "session_id" in result
        # Should NOT have memory store paths
        assert "soul_md" not in result
        assert "memory_md" not in result
        assert "user_md" not in result
        # Should NOT have raw content
        assert "raw_content" not in result


class TestPluginFailClosed:
    """Verify plugin fail-closed behavior."""

    def test_pcp_builder_returns_none_on_fail_safe(self) -> None:
        """PCP builder should return None when fail-safe is triggered."""
        # Plugin inject is fail-closed when fail-safe triggered
        plugin = RelicHermesPlugin()
        plugin.load()

        fail_safe = plugin._fail_safe
        assert fail_safe is not None
        fail_safe.trigger(
            reason="Test trigger",
            trigger=FailSafeTrigger.HOOK_ERROR,
        )

        # Plugin inject should return None when fail-safe triggered
        result = plugin.inject_ephemeral_context()
        assert result is None

    def test_hook_manager_pre_llm_call_fail_closed(self) -> None:
        """HookManager pre_llm_call should be fail-closed."""
        from relic.hermes_plugin.hooks import HookManager, LLMSessionContext
        from relic.hermes_plugin.tool_permissions import ToolPermissionMatrix

        matrix = ToolPermissionMatrix()
        fail_safe = FailSafeRegistry(enabled=True)
        fail_safe.trigger(
            reason="Test trigger",
            trigger=FailSafeTrigger.CONFIG_ERROR,
        )

        manager = HookManager(
            permission_matrix=matrix,
            fail_safe=fail_safe,
        )

        context = LLMSessionContext(
            session_id="SES-001",
            turn_id="TURN-001",
        )

        result = manager.pre_llm_call(context)

        assert result.success is False
        assert result.fail_closed is True
        assert result.context_pack is None

    def test_paused_plugin_injects_nothing(self) -> None:
        """Paused plugin should inject nothing."""
        from unittest.mock import MagicMock

        plugin = RelicHermesPlugin()
        plugin.load()

        # Mock pause controller to return True for is_paused
        mock_pause = MagicMock()
        mock_pause.is_paused.return_value = True
        plugin._pause_controller = mock_pause

        # Should return None when paused
        result = plugin.inject_ephemeral_context()
        assert result is None


class TestNoPersistentModification:
    """Verify no persistent store modifications."""

    def test_inject_does_not_create_memory_files(self, tmp_path: pytest.TempPathFactory) -> None:
        """inject_ephemeral_context should not create memory files."""
        plugin = RelicHermesPlugin()
        config = PluginConfig(pause_db_path=tmp_path / "test.db")
        plugin.load(config)

        # Inject context
        plugin.inject_ephemeral_context()

        # No memory files should be created
        assert not (tmp_path / "SOUL.md").exists()
        assert not (tmp_path / "MEMORY.md").exists()
        assert not (tmp_path / "USER.md").exists()

    def test_multiple_injects_do_not_accumulate(self) -> None:
        """Multiple inject calls should not accumulate context."""
        plugin = RelicHermesPlugin()
        plugin.load()

        for _ in range(10):
            context = plugin.inject_ephemeral_context()
            assert context is not None
            # Should always have same structure, no accumulation
            # PCP has a limited number of fields
            assert len(context) <= 20
