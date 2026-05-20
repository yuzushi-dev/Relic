"""Tests for scripts/eval_run.py CLI contract."""

from __future__ import annotations

import json

from scripts import eval_run


def test_eval_run_module_gumi_roleplay_outputs_nonzero_scenarios(capsys):
    """The documented --module gumi_roleplay flag runs real fixtures."""
    exit_code = eval_run.main(["--module", "gumi_roleplay", "--json"])

    assert exit_code in (0, 1)
    output = json.loads(capsys.readouterr().out)
    assert output["total_scenarios"] > 0
    assert "prompt_context_completeness" in output["gate_results"]


def test_eval_run_default_outputs_nonzero_scenarios(capsys):
    """Default eval invocation exercises at least one fixture-backed suite."""
    exit_code = eval_run.main(["--json"])

    assert exit_code in (0, 1)
    output = json.loads(capsys.readouterr().out)
    assert output["total_scenarios"] > 0
