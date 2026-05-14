"""Tests for plugin loading and lifecycle.

These tests verify:
- Plugin loads successfully
- Plugin failure produces no memory injection
- Plugin state transitions are correct
"""

from __future__ import annotations

from unittest.mock import MagicMock

from relic.hermes_plugin.plugin import (
    PluginConfig,
    PluginState,
    RelicHermesPlugin,
)


class TestPluginLoad:
    """Test plugin loading and initialization."""

    def test_plugin_starts_unloaded(self) -> None:
        """Plugin should start in UNLOADED state."""
        plugin = RelicHermesPlugin()
        assert plugin.state == PluginState.UNLOADED

    def test_plugin_loads_with_default_config(self) -> None:
        """Plugin should load with default configuration."""
        plugin = RelicHermesPlugin()
        result = plugin.load()
        assert result.success is True
        assert plugin.state == PluginState.LOADED

    def test_plugin_loads_with_explicit_config(self) -> None:
        """Plugin should load with explicit PluginConfig."""
        plugin = RelicHermesPlugin()
        config = PluginConfig(
            enabled=True,
            privacy_gateway_enabled=True,
            policy_version="1.0.0",
        )
        result = plugin.load(config)
        assert result.success is True
        assert plugin.plugin_id is not None

    def test_plugin_loads_with_dict_config(self) -> None:
        """Plugin should load with dict configuration."""
        plugin = RelicHermesPlugin()
        config = {
            "enabled": True,
            "privacy_gateway_enabled": True,
            "policy_version": "1.0.0",
        }
        result = plugin.load(config)
        assert result.success is True

    def test_plugin_load_failure_is_recorded(self) -> None:
        """Plugin load failure should be recorded."""
        plugin = RelicHermesPlugin()
        # Attempt to load with invalid config type
        result = plugin.load("invalid")
        assert result.success is False
        assert plugin.state == PluginState.FAILED
        assert result.error_message is not None

    def test_plugin_unload_clears_state(self) -> None:
        """Plugin unload should clear cached state."""
        plugin = RelicHermesPlugin()
        plugin.load()
        assert plugin.state == PluginState.LOADED
        plugin.unload()
        assert plugin.state == PluginState.UNLOADED

    def test_plugin_shutdown_transitions_state(self) -> None:
        """Plugin shutdown should transition to SHUTDOWN state."""
        plugin = RelicHermesPlugin()
        plugin.load()
        plugin.shutdown()
        assert plugin.state == PluginState.SHUTDOWN


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
        plugin.load("invalid")  # Force failure
        assert plugin.state == PluginState.FAILED
        # Should still return None
        result = plugin.inject_ephemeral_context()
        assert result is None

    def test_inject_context_when_disabled_returns_none(self) -> None:
        """When disabled, inject_ephemeral_context should return None."""
        plugin = RelicHermesPlugin()
        config = PluginConfig(enabled=False)
        plugin.load(config)
        assert plugin.state == PluginState.LOADED
        result = plugin.inject_ephemeral_context()
        assert result is None

    def test_inject_context_when_paused_returns_none(self) -> None:
        """When paused, inject_ephemeral_context should return None."""
        plugin = RelicHermesPlugin()
        config = PluginConfig(enabled=True)
        plugin.load(config)

        # Mock the pause controller to simulate paused state
        mock_pause = MagicMock()
        mock_pause.is_paused.return_value = True
        plugin._pause_controller = mock_pause

        result = plugin.inject_ephemeral_context()
        assert result is None

    def test_inject_context_returns_ephemeral_only(self) -> None:
        """inject_ephemeral_context should return PCP data only."""
        plugin = RelicHermesPlugin()
        plugin.load()
        result = plugin.inject_ephemeral_context()
        assert result is not None
        # Should have PCP fields
        assert "schema_version" in result
        assert "pack_id" in result
        # Should NOT have memory store paths
        assert "soul_md" not in result
        assert "memory_md" not in result
        assert "user_md" not in result


class TestPluginHealthCheck:
    """Test plugin health check functionality."""

    def test_health_check_returns_status(self) -> None:
        """Health check should return current status."""
        plugin = RelicHermesPlugin()
        plugin.load()
        health = plugin.check_lifecycle_health()
        assert "state" in health
        assert "plugin_id" in health
        assert "is_paused" in health
        assert "config_enabled" in health

    def test_health_check_when_unloaded(self) -> None:
        """Health check should work even when unloaded."""
        plugin = RelicHermesPlugin()
        health = plugin.check_lifecycle_health()
        assert health["state"] == PluginState.UNLOADED.value
        assert health["is_paused"] is False
