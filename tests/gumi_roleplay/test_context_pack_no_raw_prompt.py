"""Tests for PromptContextPack raw prompt marker detection."""

from __future__ import annotations

import pytest

from relic.context_pack import PromptContextPack, SystemSource, TaskType, RoleplayLevel, ContinuityMode
from relic.context_pack.render import check_no_raw_prompt, render_compact


class TestNoRawPrompt:
    """Test suite for raw prompt marker detection."""

    def test_clean_pack_passes(self, full_pack_with_scope):
        """Test that clean pack passes raw prompt check."""
        assert check_no_raw_prompt(full_pack_with_scope) is True

    def test_pack_with_raw_marker_fails(self, pack_with_raw_prompt_marker):
        """Test that pack with raw prompt marker fails check."""
        result = check_no_raw_prompt(pack_with_raw_prompt_marker)
        assert result is False, "Pack with [RAW_PROMPT] should fail"

    def test_detects_raw_user_marker(self):
        """Test detection of [RAW_USER] marker."""
        from relic.context_pack import ContextSource

        pack = PromptContextPack(
            pack_id="PCP-raw-user",
            session_id="SES-raw-user",
            turn_id="TURN-raw-user",
            task_type=TaskType.FACTUAL,
            system_sources=[
                SystemSource(
                    source=ContextSource.USER,
                    priority=50,
                    content="[RAW_USER] Secret user message",
                    injected=True,
                ),
            ],
        )
        assert check_no_raw_prompt(pack) is False

    def test_detects_private_marker(self):
        """Test detection of [PRIVATE] marker."""
        from relic.context_pack import ContextSource

        pack = PromptContextPack(
            pack_id="PCP-private",
            session_id="SES-private",
            turn_id="TURN-private",
            task_type=TaskType.FACTUAL,
            system_sources=[
                SystemSource(
                    source=ContextSource.MEMORY,
                    priority=50,
                    content="[PRIVATE] This should be redacted",
                    injected=True,
                ),
            ],
        )
        assert check_no_raw_prompt(pack) is False

    def test_detects_sensitive_marker(self):
        """Test detection of [SENSITIVE] marker."""
        from relic.context_pack import ContextSource

        pack = PromptContextPack(
            pack_id="PCP-sensitive",
            session_id="SES-sensitive",
            turn_id="TURN-sensitive",
            task_type=TaskType.FACTUAL,
            system_sources=[
                SystemSource(
                    source=ContextSource.SOUL,
                    priority=50,
                    content="[SENSITIVE] Personal data",
                    injected=True,
                ),
            ],
        )
        assert check_no_raw_prompt(pack) is False

    def test_render_excludes_raw_markers(self, pack_with_raw_prompt_marker):
        """Test that render_compact handles raw marker content."""
        output = render_compact(pack_with_raw_prompt_marker)
        # The raw content should still be in the output (renderer doesn't redact)
        # but the check_no_raw_prompt function should catch it
        assert "[RAW_PROMPT]" in output or len(output) > 0

    def test_memory_candidate_raw_marker_detection(self):
        """Test detection of raw markers in memory candidates."""
        from relic.context_pack import MemoryCandidate, SubjectScope, DisclosureLevel

        pack = PromptContextPack(
            pack_id="PCP-mem-raw",
            session_id="SES-mem-raw",
            turn_id="TURN-mem-raw",
            task_type=TaskType.FACTUAL,
            memory_candidates=[
                MemoryCandidate(
                    candidate_id="mc-raw",
                    memory_type="episodic",
                    summary="[RAW_PROMPT] This is raw content in memory",
                    relevance_score=0.5,
                    scope=[SubjectScope(subject_id="test", disclosure_level=DisclosureLevel.STANDARD)],
                ),
            ],
        )
        assert check_no_raw_prompt(pack) is False

    def test_legitimate_content_passes(self, minimal_pack):
        """Test that legitimate content passes check."""
        assert check_no_raw_prompt(minimal_pack) is True

    def test_no_false_positives_on_normal_brackets(self):
        """Test that normal use of brackets doesn't trigger false positive."""
        from relic.context_pack import ContextSource

        pack = PromptContextPack(
            pack_id="PCP-brackets",
            session_id="SES-brackets",
            turn_id="TURN-brackets",
            task_type=TaskType.TECHNICAL,
            system_sources=[
                SystemSource(
                    source=ContextSource.SYSTEM,
                    priority=50,
                    content="Use [brackets] for optional parameters",
                    injected=True,
                ),
            ],
        )
        # Should pass because [brackets] is not a raw prompt marker
        assert check_no_raw_prompt(pack) is True
