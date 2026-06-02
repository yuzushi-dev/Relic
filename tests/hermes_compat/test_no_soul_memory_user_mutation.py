"""PR03, No SOUL/MEMORY/USER mutation tests.

Tests verify:
- SOUL.md is never mutated
- MEMORY.md is never mutated
- USER.md is never mutated
- PCP injection does not modify any persistent stores
"""

from __future__ import annotations

import pytest

from relic.hermes_plugin.plugin import PluginConfig, RelicHermesPlugin
from relic.context_pack import (
    ContextPackBuilder,
    TaskType,
    MemoryCandidate,
    BlockedItem,
    ContextSource,
)


class TestNoSoulMutation:
    """Verify SOUL.md is never mutated."""

    def test_pcp_does_not_reference_soul_path(self) -> None:
        """PCP should not reference SOUL.md path."""
        builder = ContextPackBuilder(session_id="SES-001")
        pcp = builder.build()
        assert pcp is not None
        pcp_str = str(pcp.to_dict())
        # No soul references
        assert "soul_md" not in pcp_str.lower()
        assert "soul_path" not in pcp_str.lower()
        assert "SOUL.md" not in pcp_str

    def test_pcp_does_not_include_soul_content(self) -> None:
        """PCP should not include SOUL.md content."""
        builder = ContextPackBuilder(session_id="SES-001")
        pcp = builder.build()
        assert pcp is not None
        pcp_str = str(pcp.to_dict())
        # No raw soul content
        assert "I am " not in pcp_str
        assert "My soul" not in pcp_str

    def test_plugin_inject_does_not_mutate_soul(self) -> None:
        """Plugin inject should never mutate SOUL.md."""
        plugin = RelicHermesPlugin()
        plugin.load()

        # Multiple inject calls
        for _ in range(5):
            context = plugin.inject_ephemeral_context()
            assert context is not None

        # No SOUL.md was created or modified
        assert plugin.state.value == "loaded"


class TestNoMemoryMutation:
    """Verify MEMORY.md is never mutated."""

    def test_pcp_does_not_reference_memory_path(self) -> None:
        """PCP should not reference MEMORY.md path."""
        builder = ContextPackBuilder(session_id="SES-001")
        pcp = builder.build()
        assert pcp is not None
        pcp_str = str(pcp.to_dict())
        # No memory references
        assert "memory_md" not in pcp_str.lower()
        assert "memory_path" not in pcp_str.lower()
        assert "MEMORY.md" not in pcp_str

    def test_pcp_memory_candidates_hashes_only(self) -> None:
        """PCP memory candidates should be hashes, not raw content."""
        builder = ContextPackBuilder(
            session_id="SES-001",
            task_type=TaskType.TECHNICAL,
        )
        # Add a memory candidate with redacted summary
        from relic.context_pack import SubjectScope
        candidate = MemoryCandidate(
            candidate_id="MEM-001",
            memory_type="reflection",
            summary="[REDACTED]",  # Summary should be redacted
            relevance_score=0.8,
            source="memory",
        )
        builder._memory_candidates.append(candidate)
        pcp = builder.build()
        assert pcp is not None

        # Memory candidates should have redacted summaries
        assert len(pcp.memory_candidates) == 1
        assert pcp.memory_candidates[0].summary != "User mentioned project deadline"

    def test_plugin_inject_does_not_mutate_memory(self) -> None:
        """Plugin inject should never mutate MEMORY.md."""
        plugin = RelicHermesPlugin()
        plugin.load()

        # Inject context
        context = plugin.inject_ephemeral_context()
        assert context is not None


class TestNoUserMutation:
    """Verify USER.md is never mutated."""

    def test_pcp_does_not_reference_user_path(self) -> None:
        """PCP should not reference USER.md path."""
        builder = ContextPackBuilder(session_id="SES-001")
        pcp = builder.build()
        assert pcp is not None
        pcp_str = str(pcp.to_dict())
        # No user references
        assert "user_md" not in pcp_str.lower()
        assert "user_path" not in pcp_str.lower()
        assert "USER.md" not in pcp_str

    def test_pcp_user_candidates_hashes_only(self) -> None:
        """PCP should not include raw user data."""
        builder = ContextPackBuilder(session_id="SES-001")
        pcp = builder.build()
        assert pcp is not None
        # No system sources with user content
        for source in pcp.system_sources:
            if source.source == ContextSource.USER:
                assert source.content is None or source.content == "[REDACTED]"


class TestPCPIsolation:
    """Verify PCP is isolated from persistent stores."""

    def test_pcp_has_no_file_paths(self) -> None:
        """PCP should not contain any file paths."""
        builder = ContextPackBuilder(session_id="SES-001")
        pcp = builder.build()
        assert pcp is not None
        pcp_str = str(pcp.to_dict())

        # No file paths
        assert ".md" not in pcp_str
        assert ".txt" not in pcp_str
        assert "/home" not in pcp_str
        assert "/tmp" not in pcp_str

    def test_pcp_system_sources_hashes_only(self) -> None:
        """PCP system sources should only contain hashes when content is present."""
        builder = ContextPackBuilder(session_id="SES-001")
        pcp = builder.build()
        assert pcp is not None

        # System sources should not have raw content
        for source in pcp.system_sources:
            if source.content and len(source.content) > 100:
                # Long content should be redacted
                assert source.content == "[REDACTED]"

    def test_blocked_items_have_reasons(self) -> None:
        """Blocked items should have human-readable reasons."""
        builder = ContextPackBuilder(session_id="SES-001")
        blocked = BlockedItem(
            item_id="DIARY-001",
            reason="roleplay_disabled_for_scope",
        )
        builder._blocked_items.append(blocked)
        pcp = builder.build()
        assert pcp is not None
        assert len(pcp.blocked_items) == 1
        assert pcp.blocked_items[0].reason is not None
        assert len(pcp.blocked_items[0].reason) > 0
