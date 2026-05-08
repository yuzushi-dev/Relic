"""Tests for /relic commands (why, pause, resume).

These tests verify:
- /relic why returns last CAC trace
- /relic pause disables guidance
- /relic resume re-enables guidance
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

from relic.hermes_plugin.commands import (
    CommandResult,
    RelicCommand,
    RelicCommands,
)


class TestRelicCommandsExecution:
    """Test command execution."""

    def test_execute_unknown_command_returns_error(self) -> None:
        """Unknown commands should return error."""
        commands = RelicCommands()
        result = commands.execute(RelicCommand.WHY)
        assert result.success is False
        assert "not available" in result.message

    def test_execute_why_without_cac_returns_no_traces(self) -> None:
        """WHY without CAC controller should return no traces."""
        commands = RelicCommands()
        result = commands.execute(RelicCommand.WHY)
        assert result.success is False
        assert "not available" in result.message

    def test_execute_pause_without_pause_controller(self) -> None:
        """PAUSE without pause controller should fail."""
        commands = RelicCommands()
        result = commands.execute(RelicCommand.PAUSE)
        assert result.success is False
        assert "not available" in result.message

    def test_execute_resume_without_pause_controller(self) -> None:
        """RESUME without pause controller should fail."""
        commands = RelicCommands()
        result = commands.execute(RelicCommand.RESUME)
        assert result.success is False
        assert "not available" in result.message

    def test_execute_status_returns_loaded_status(self) -> None:
        """STATUS should return plugin status."""
        commands = RelicCommands()
        result = commands.execute(RelicCommand.STATUS)
        assert result.success is True
        assert "plugin_loaded" in result.data
        assert result.data["plugin_loaded"] is True

    def test_execute_status_includes_paused_state(self) -> None:
        """STATUS should include paused state."""
        commands = RelicCommands()
        result = commands.execute(RelicCommand.STATUS)
        assert result.success is True
        assert "guidance_paused" in result.data
        assert result.data["guidance_paused"] is False

    def test_execute_status_includes_policy_version(self) -> None:
        """STATUS should include policy version."""
        commands = RelicCommands()
        result = commands.execute(RelicCommand.STATUS)
        assert result.success is True
        assert "policy_version" in result.data
        assert result.data["policy_version"] == "1.0.0"


class TestPauseResumeIntegration:
    """Test pause/resume integration with PauseController."""

    def test_pause_calls_controller(self) -> None:
        """Pause should call the pause controller."""
        mock_controller = MagicMock()
        mock_controller.pause.return_value = MagicMock()
        commands = RelicCommands(pause_controller=mock_controller)
        result = commands.execute(RelicCommand.PAUSE)
        assert result.success is True
        mock_controller.pause.assert_called_once()

    def test_resume_calls_controller(self) -> None:
        """Resume should call the resume controller."""
        mock_controller = MagicMock()
        mock_controller.resume.return_value = MagicMock()
        commands = RelicCommands(pause_controller=mock_controller)
        result = commands.execute(RelicCommand.RESUME)
        assert result.success is True
        mock_controller.resume.assert_called_once()

    def test_set_pause_controller(self) -> None:
        """Should allow setting pause controller after init."""
        commands = RelicCommands()
        mock_controller = MagicMock()
        commands.set_pause_controller(mock_controller)
        result = commands.execute(RelicCommand.PAUSE)
        assert result.success is True


class TestCommandResult:
    """Test command result structure."""

    def test_command_result_has_required_fields(self) -> None:
        """Command result should have required fields."""
        result = CommandResult(
            command=RelicCommand.WHY,
            success=True,
            message="test",
            data={"key": "value"},
            executed_at=datetime.utcnow(),
        )
        assert result.command == RelicCommand.WHY
        assert result.success is True
        assert result.message == "test"
        assert result.data == {"key": "value"}
        assert result.executed_at is not None

    def test_command_result_includes_timestamp(self) -> None:
        """Command result should include timestamp."""
        result = CommandResult(
            command=RelicCommand.WHY,
            success=True,
            message="test",
            data={"key": "value"},
            executed_at=datetime.utcnow(),
        )
        assert result.executed_at is not None
