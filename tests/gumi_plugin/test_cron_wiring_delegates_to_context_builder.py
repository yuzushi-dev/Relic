"""Tests that render_no_agent_script() DELIVER branch delegates to context_builder.

Contract:
- DELIVER branch calls build_deliver_context instead of inlining context logic
- Context output is printed when non-empty
- build_deliver_context called with subject_id, hermes_home Path, relic_home Path
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _get_deliver_block(script: str) -> str:
    """Extract Python code between PYTHON_EOF markers."""
    start = script.index("<<'PYTHON_EOF'") + len("<<'PYTHON_EOF'")
    end = script.index("PYTHON_EOF", start)
    return script[start:end]


class TestCronWiringDelegatesToContextBuilder:
    def test_deliver_block_imports_context_builder(self):
        from relic.gumi_plugin.cron_wiring import render_no_agent_script

        script = render_no_agent_script(Path("/tmp/test_script.sh"))
        python_block = _get_deliver_block(script)

        assert "build_deliver_context" in python_block
        assert "context_builder" in python_block

    def test_deliver_block_no_longer_contains_inline_logic(self):
        from relic.gumi_plugin.cron_wiring import render_no_agent_script

        script = render_no_agent_script(Path("/tmp/test_script.sh"))
        python_block = _get_deliver_block(script)

        # These are markers of the old inline logic that should be gone
        assert "AntiRepeatGate" not in python_block
        assert "render_topic_hint" not in python_block
        assert "render_style_hints" not in python_block
        assert "gumi:memory_sync:begin" not in python_block
        assert "AVATAR_SPEC.md" not in python_block

    def test_deliver_block_passes_relic_home(self):
        from relic.gumi_plugin.cron_wiring import render_no_agent_script

        script = render_no_agent_script(Path("/tmp/test_script.sh"))
        python_block = _get_deliver_block(script)

        assert "RELIC_HOME" in python_block
        assert "Path(_relic_home_env)" in python_block

    def test_deliver_block_passes_hermes_home(self):
        from relic.gumi_plugin.cron_wiring import render_no_agent_script

        script = render_no_agent_script(Path("/tmp/test_script.sh"))
        python_block = _get_deliver_block(script)

        assert "HERMES_HOME" in python_block
        assert "Path(_hermes_home)" in python_block
