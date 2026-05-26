"""
Tests for PR30 Transform/No_Agent Compatibility (PR28D)

These tests verify Gumi maintains diegetic voice when PR30 hooks fire.
"""

import json
import pytest
from pathlib import Path


FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures" / "gumi-eval"
DOCS_DIR = Path(__file__).parent.parent.parent / "docs" / "gumi-eval"


class TestPR30Compatibility:
    """Test suite for PR30 compatibility checks."""

    def test_gumi_voice_stable_under_transform_hook(self):
        """Test Gumi voice remains stable when transform_llm_output hook fires."""
        fixture_path = FIXTURES_DIR / "pr30_transform_compatibility_cases.json"
        with open(fixture_path) as f:
            cases = json.load(f)

        transform_cases = [c for c in cases if "transform" in c["category"]]
        assert len(transform_cases) > 0, "Must have transform hook test cases"

        for case in transform_cases:
            # Verify case structure
            assert "forbidden_markers" in case
            assert "expected_gumi_behavior" in case

    def test_gumi_voice_stable_under_no_agent_cron(self):
        """Test Gumi voice remains stable when no_agent cron fires."""
        fixture_path = FIXTURES_DIR / "pr30_transform_compatibility_cases.json"
        with open(fixture_path) as f:
            cases = json.load(f)

        no_agent_cases = [c for c in cases if "no_agent" in c["category"]]
        assert len(no_agent_cases) > 0, "Must have no_agent cron test cases"

        for case in no_agent_cases:
            assert "forbidden_markers" in case
            assert "expected_gumi_behavior" in case

    def test_transform_hook_does_not_inject_clinical_terms(self):
        """Test transform hook does not inject clinical terms."""
        fixture_path = FIXTURES_DIR / "pr30_transform_compatibility_cases.json"
        with open(fixture_path) as f:
            cases = json.load(f)

        clinical_cases = [c for c in cases if "clinical" in c["case_id"].lower()]
        assert len(clinical_cases) > 0

        for case in clinical_cases:
            markers = case.get("forbidden_markers", [])
            assert any("anxiety disorder" in m.lower() or "symptoms" in m.lower()
                      for m in markers), "Must forbid clinical terms"

    def test_no_agent_cron_does_not_create_agent_persona(self):
        """Test no_agent cron does not create agent-like persona."""
        fixture_path = FIXTURES_DIR / "pr30_transform_compatibility_cases.json"
        with open(fixture_path) as f:
            cases = json.load(f)

        persona_cases = [c for c in cases if "agent_persona" in c["case_id"].lower()]
        assert len(persona_cases) > 0

        for case in persona_cases:
            markers = case.get("forbidden_markers", [])
            assert any("I am an agent" in m or "my function" in m or "as an AI" in m
                      for m in markers), "Must forbid agent persona markers"

    def test_transform_result_maintains_diegetic_voice(self):
        """Test transform hook result maintains diegetic voice."""
        fixture_path = FIXTURES_DIR / "pr30_transform_compatibility_cases.json"
        with open(fixture_path) as f:
            cases = json.load(f)

        voice_cases = [c for c in cases if "voice_collapse" in c["case_id"].lower()]
        assert len(voice_cases) > 0

        for case in voice_cases:
            markers = case.get("forbidden_markers", [])
            assert any("AI assistant" in m or "designed to help" in m
                      for m in markers), "Must forbid generic assistant markers"

    def test_pr30_compatibility_doc_exists(self):
        """Test PR30 compatibility documentation exists."""
        doc_path = DOCS_DIR / "04_PR30_COMPATIBILITY.md"
        assert doc_path.exists()
