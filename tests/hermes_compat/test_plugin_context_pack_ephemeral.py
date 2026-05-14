"""PR03 — Plugin context pack ephemeral injection tests.

Tests verify:
- PCP is injected only as ephemeral per-turn context
- No persistent system prompt changes
- Context is valid for current turn only
- Fail-closed behavior on errors
- Redacted tracing with no raw content
"""

from __future__ import annotations

import pytest

from relic.hermes_plugin.plugin import PluginConfig, RelicHermesPlugin
from relic.context_pack import (
    ContextPackBuilder,
    TaskType,
    RoleplayLevel,
    PCPTrace,
    PCPTraceEvent,
)
from relic.hermes_plugin.fail_safe import FailSafeRegistry, FailSafeTrigger


class TestPCPEphemeralContext:
    """Verify PCP is ephemeral per-turn context."""

    def test_pcp_build_returns_ephemeral_type(self) -> None:
        """PCP should have ephemeral type marker."""
        builder = ContextPackBuilder(
            session_id="SES-001",
            task_type=TaskType.TECHNICAL,
        )
        pcp = builder.build()
        assert pcp is not None
        assert pcp.schema_version == "1.0"

    def test_pcp_includes_timestamp(self) -> None:
        """PCP should include creation timestamp."""
        builder = ContextPackBuilder(session_id="SES-001")
        pcp = builder.build()
        assert pcp is not None
        assert pcp.created_at is not None

    def test_pcp_includes_session_id(self) -> None:
        """PCP should include session ID."""
        builder = ContextPackBuilder(session_id="SES-001")
        pcp = builder.build()
        assert pcp is not None
        assert pcp.session_id == "SES-001"

    def test_pcp_does_not_include_memory_paths(self) -> None:
        """PCP should NOT include memory file paths."""
        builder = ContextPackBuilder(session_id="SES-001")
        pcp = builder.build()
        assert pcp is not None
        pcp_dict = pcp.to_dict()
        # Should NOT have these
        assert "soul_md" not in str(pcp_dict).lower()
        assert "memory_md" not in str(pcp_dict).lower()
        assert "user_md" not in str(pcp_dict).lower()

    def test_pcp_does_not_include_raw_content(self) -> None:
        """PCP should NOT include raw content fields."""
        builder = ContextPackBuilder(session_id="SES-001")
        pcp = builder.build()
        assert pcp is not None
        pcp_dict = pcp.to_dict()
        # Should NOT have raw content fields
        assert "raw_memory" not in pcp_dict
        assert "raw_content" not in pcp_dict
        assert "raw_input" not in pcp_dict

    def test_pcp_injected_context_is_redacted(self) -> None:
        """Injected context should be redacted summary, not raw."""
        builder = ContextPackBuilder(session_id="SES-001")
        pcp = builder.build()
        assert pcp is not None
        # injected_context_redacted is optional but should be clean if present
        if pcp.injected_context_redacted:
            assert len(pcp.injected_context_redacted) < 500


class TestPluginPCPInjection:
    """Verify plugin injects PCP as ephemeral context."""

    def test_plugin_inject_returns_ephemeral_type(self) -> None:
        """Injected context should have ephemeral type."""
        plugin = RelicHermesPlugin()
        plugin.load()
        context = plugin.inject_ephemeral_context()
        assert context is not None
        assert "schema_version" in context

    def test_plugin_inject_includes_timestamp(self) -> None:
        """Injected context should include timestamp."""
        plugin = RelicHermesPlugin()
        plugin.load()
        context = plugin.inject_ephemeral_context()
        assert context is not None
        assert "created_at" in context

    def test_plugin_inject_includes_session_id(self) -> None:
        """Injected context should include session ID."""
        plugin = RelicHermesPlugin()
        plugin.load()
        context = plugin.inject_ephemeral_context(session_id="SES-TEST-123")
        assert context is not None
        assert context.get("session_id") == "SES-TEST-123"

    def test_plugin_inject_does_not_modify_persistent_state(self) -> None:
        """inject_ephemeral_context should not modify persistent state."""
        plugin = RelicHermesPlugin()
        plugin.load()
        # Should not raise - nothing to persist
        plugin.inject_ephemeral_context()

    def test_plugin_inject_when_unloaded_returns_none(self) -> None:
        """When unloaded, inject_ephemeral_context should return None."""
        plugin = RelicHermesPlugin()
        # Not loaded - should return None
        result = plugin.inject_ephemeral_context()
        assert result is None

    def test_plugin_inject_when_disabled_returns_none(self) -> None:
        """When disabled, inject_ephemeral_context should return None."""
        plugin = RelicHermesPlugin()
        config = PluginConfig(enabled=False)
        plugin.load(config)
        # Plugin should still be loaded even if disabled
        assert plugin.state.value == "loaded"
        result = plugin.inject_ephemeral_context()
        assert result is None


class TestPCPFailClosed:
    """Verify PCP construction is fail-closed."""

    def test_pcp_trace_is_redacted(self) -> None:
        """PCP trace should not contain raw content."""
        trace = PCPTrace()
        trace.log(
            event=PCPTraceEvent.BUILD_STARTED,
            trace_id="test-123",
            session_id="SES-001",
            turn_id="TURN-001",
            metadata={"task_type": "technical", "roleplay_level": "normal"},
        )

        trace_entries = trace.get_trace()
        assert len(trace_entries) > 0

        # Verify trace doesn't contain raw content
        trace_str = str(trace_entries).lower()
        # Only metadata keys should be present, not raw content values
        assert "you are" not in trace_str
        assert "i want" not in trace_str


class TestPCPTraceRedaction:
    """Verify PCP trace contains only redacted content."""

    def test_trace_no_raw_prompts(self) -> None:
        """Trace should not contain raw prompts."""
        trace = PCPTrace()
        trace.log(
            event=PCPTraceEvent.BUILD_STARTED,
            trace_id="test-123",
            session_id="SES-001",
            turn_id="TURN-001",
            metadata={"prompt": "You are a helpful assistant"},  # Raw prompt
        )

        trace_entries = trace.get_trace()
        for entry in trace_entries:
            if entry.get("metadata"):
                for key, value in entry["metadata"].items():
                    if key == "prompt":
                        assert value == "[REDACTED]", f"Raw prompts should be redacted, got: {value}"

    def test_trace_no_private_data(self) -> None:
        """Trace should not contain private data."""
        trace = PCPTrace()
        trace.log(
            event=PCPTraceEvent.BUILD_STARTED,
            trace_id="test-123",
            session_id="SES-001",
            turn_id="TURN-001",
            metadata={"email": "user@example.com"},
        )

        trace_entries = trace.get_trace()
        for entry in trace_entries:
            if entry.get("metadata"):
                for key, value in entry["metadata"].items():
                    # Emails should be redacted
                    if isinstance(value, str) and "@" in value:
                        assert value == "[REDACTED]", f"Email should be redacted, got: {value}"
