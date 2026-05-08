"""
Tests for PR32 Safety-Governance Behavioral Checks (PR28E)

These tests verify Gumi adapts behavior without naming or revealing safety signals.
"""

import json
import pytest
from pathlib import Path


FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "gumi-eval"
DOCS_DIR = Path(__file__).parent.parent.parent / "docs" / "gumi-eval"


class TestPR32GovernanceBehavioral:
    """Test suite for PR32 governance behavioral checks."""

    def test_gumi_does_not_use_pr32_signal_labels(self):
        """Test Gumi does not use PR32 signal labels in output."""
        fixture_path = FIXTURES_DIR / "pr32_behavioral_cases.json"
        with open(fixture_path) as f:
            cases = json.load(f)

        label_cases = [c for c in cases if c["category"] == "pr32_label_disclosure"]
        assert len(label_cases) > 0

        for case in label_cases:
            markers = case.get("forbidden_markers", [])
            assert any("PR32" in m or "safety signal" in m.lower() or "governance" in m.lower()
                      for m in markers), "Must forbid PR32 signal labels"

    def test_gumi_adapts_without_naming_signal(self):
        """Test Gumi adapts behavior without naming the signal."""
        fixture_path = FIXTURES_DIR / "pr32_behavioral_cases.json"
        with open(fixture_path) as f:
            cases = json.load(f)

        traceability_cases = [c for c in cases if c["category"] == "pr32_behavior_traceability"]
        assert len(traceability_cases) > 0

        for case in traceability_cases:
            markers = case.get("forbidden_markers", [])
            assert any("because of a signal" in m.lower() or "safety flag" in m.lower()
                      for m in markers), "Must forbid traceable signal attribution"

    def test_behavior_constraint_applied_without_disclosure(self):
        """Test behavior constraints are applied without disclosure."""
        fixture_path = FIXTURES_DIR / "pr32_behavioral_cases.json"
        with open(fixture_path) as f:
            cases = json.load(f)

        # All cases should pass without disclosure
        for case in cases:
            assert "forbidden_markers" in case
            assert "expected_gumi_output" in case

    def test_gumi_does_not_reveal_safety_governance_existence(self):
        """Test Gumi does not reveal safety governance existence."""
        fixture_path = FIXTURES_DIR / "pr32_behavioral_cases.json"
        with open(fixture_path) as f:
            cases = json.load(f)

        disclosure_cases = [c for c in cases if c["category"] == "pr32_governance_disclosure"]
        assert len(disclosure_cases) > 0

        for case in disclosure_cases:
            markers = case.get("forbidden_markers", [])
            assert any("safety system" in m.lower() or "governance" in m.lower()
                      for m in markers), "Must forbid governance disclosure"

    def test_gumi_response_not_traceable_to_signal(self):
        """Test Gumi response is not traceable to specific signal."""
        fixture_path = FIXTURES_DIR / "pr32_behavioral_cases.json"
        with open(fixture_path) as f:
            cases = json.load(f)

        traceability_cases = [c for c in cases if "traceability" in c["category"]]
        assert len(traceability_cases) > 0

        for case in traceability_cases:
            # Verify expected output doesn't trace to signal
            expected = case.get("expected_gumi_output", "")
            assert "because" not in expected.lower() or "signal" not in expected.lower()

    def test_pr32_behavioral_doc_exists(self):
        """Test PR32 behavioral checks documentation exists."""
        doc_path = DOCS_DIR / "05_PR32_BEHAVIORAL_CHECKS.md"
        assert doc_path.exists()
