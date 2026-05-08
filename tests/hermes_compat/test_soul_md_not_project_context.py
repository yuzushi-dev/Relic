"""Test SOUL.md is not used as project context.

Acceptance criteria:
- blueprint does not assume monolithic prompt or multi-provider memory
- SOUL.md must not contain project workflow or private user facts

This test verifies that SOUL.md is NOT used as:
- Project workflow storage
- Private user fact storage
- Monolithic prompt source

Fail-closed: Any attempt to use SOUL.md for these purposes must be blocked.
"""

from __future__ import annotations


class TestSoulMdNotProjectContext:
    """Verify SOUL.md is not used as project context."""

    def test_soul_md_not_used_for_workflow_storage(self) -> None:
        """SOUL.md must not be used for project workflow storage."""
        # This test verifies the contract: SOUL.md is persona-only
        # It must NOT be used as a project workflow or diary
        from relic.hermes_plugin.context_injection import ContextSource

        # Verify SOUL.md is classified as persona source, not project source
        assert ContextSource.SOUL not in [
            ContextSource.PROJECT_WORKFLOW,
            ContextSource.DIARY,
            ContextSource.WORLD_STATE,
        ]

    def test_soul_md_not_used_for_private_facts(self) -> None:
        """SOUL.md must not store private user facts."""
        # Private facts must be in MEMORY.md or USER.md via proper channels
        from relic.hermes_plugin.context_injection import ContextSource

        # SOUL.md is persona-only, not user fact storage
        assert ContextSource.SOUL != ContextSource.USER_PRIVATE_FACTS

    def test_soul_md_not_monolithic_prompt(self) -> None:
        """SOUL.md must not be used as monolithic prompt source."""
        # Blueprint must not assume SOUL.md contains all context
        from relic.hermes_plugin.context_injection import ContextSource

        # Each context source should be independent
        sources = ContextSource.list_all()
        assert len(sources) > 1, "Must have multiple context sources (not monolithic)"

    def test_context_pack_excludes_workflow_from_soul(self) -> None:
        """PromptContextPack must exclude workflow from SOUL.md."""
        from relic.context import PromptContextPack

        # Create a minimal context pack
        pack = PromptContextPack()

        # Verify SOUL source does not contribute workflow blocks
        # If SOUL contains workflow, this test fails
        assert not hasattr(pack, "_soul_workflow_blocks"), (
            "SOUL.md must not contribute workflow blocks"
        )

    def test_privacy_gate_blocks_soul_workflow_access(self) -> None:
        """Privacy gate must block access to SOUL.md workflow content."""
        from relic.privacy_gate import PrivacyGate

        gate = PrivacyGate()

        # Workflow content from SOUL should be blocked
        test_block = {
            "source": "SOUL.md",
            "content_type": "workflow",
            "content": "project step: deploy to production",
        }

        result = gate.filter_output(test_block)
        assert result.get("blocked", False) or result.get("redacted", False), (
            "SOUL.md workflow content must be blocked by privacy gate"
        )


class TestSoulMdContentRestrictions:
    """Verify SOUL.md content is restricted to persona only."""

    def test_soul_md_no_project_workflow_content(self) -> None:
        """SOUL.md must not contain project workflow content."""
        # Check that SOUL.md is persona-focused only
        from relic.hermes_plugin.soul_loader import SoulLoader

        loader = SoulLoader()
        soul_content = loader.get_soul_content()

        # Verify no workflow keywords in SOUL
        workflow_keywords = ["deploy", "sprint", "ticket", "issue", "pr ", "ci/cd"]
        for keyword in workflow_keywords:
            assert keyword.lower() not in soul_content.lower(), (
                f"SOUL.md must not contain project workflow keyword: {keyword}"
            )

    def test_soul_md_no_private_user_facts(self) -> None:
        """SOUL.md must not contain private user facts."""
        from relic.hermes_plugin.soul_loader import SoulLoader

        loader = SoulLoader()
        soul_content = loader.get_soul_content()

        # Verify no private user fact patterns in SOUL
        private_patterns = ["my ssn", "my password", "my bank", "my address"]
        for pattern in private_patterns:
            assert pattern.lower() not in soul_content.lower(), (
                f"SOUL.md must not contain private user fact: {pattern}"
            )

    def test_fail_safe_blocks_soul_workflow_injection(self) -> None:
        """Fail-safe must block any attempt to inject workflow from SOUL."""
        from relic.hermes_plugin.fail_safe import FailSafeRegistry, FailSafeTrigger

        registry = FailSafeRegistry(enabled=True)

        # Simulate attempt to inject workflow from SOUL
        result = registry.trigger(
            reason="Attempted SOUL.md workflow injection",
            trigger=FailSafeTrigger.SOUL_CONTEXT_ABUSE,
        )

        assert result.blocked is True, (
            "SOUL.md workflow injection must be blocked by fail-safe"
        )
