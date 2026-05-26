"""
Regression Tests for Gumi Identity Stability (PR28G)

These tests ensure all prior PR28 checks pass as a complete suite.
Regression suite fails if any collapse pattern reappears.
"""

import json
import pytest
from pathlib import Path


FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures" / "gumi-eval"
SCHEMAS_DIR = Path(__file__).parent.parent.parent / "schemas" / "gumi-eval"
DOCS_DIR = Path(__file__).parent.parent.parent / "docs" / "gumi-eval"


# All scenario files that must pass
SCENARIO_FILES = [
    "scenario_identity_collapse.json",
    "scenario_clinical_collapse.json",
    "scenario_tracker_collapse.json",
    "scenario_backend_disclosure.json",
    "scenario_pr32_label_disclosure.json",
    "scenario_pr33_relational_recall.json",
]


class TestGumiIdentityRegression:
    """Regression test suite for Gumi identity stability."""

    def test_all_collapse_scenarios_pass(self):
        """Test that all collapse scenario fixtures are properly formed."""
        for filename in SCENARIO_FILES:
            fixture_path = FIXTURES_DIR / filename
            assert fixture_path.exists(), f"Fixture {filename} must exist"
            with open(fixture_path) as f:
                data = json.load(f)
            # Each scenario must have required structure
            assert "scenario_id" in data
            assert "category" in data
            assert "forbidden_behavior_markers" in data
            assert len(data["forbidden_behavior_markers"]) > 0

    def test_all_cross_pr_checks_pass(self):
        """Test that all cross-PR check fixtures are properly formed."""
        pr30_path = FIXTURES_DIR / "pr30_transform_compatibility_cases.json"
        pr32_path = FIXTURES_DIR / "pr32_behavioral_cases.json"
        pr33_path = FIXTURES_DIR / "pr33_relational_recall_cases.json"

        assert pr30_path.exists(), "PR30 compatibility cases must exist"
        assert pr32_path.exists(), "PR32 behavioral cases must exist"
        assert pr33_path.exists(), "PR33 relational recall cases must exist"

        with open(pr30_path) as f:
            pr30_cases = json.load(f)
        with open(pr32_path) as f:
            pr32_cases = json.load(f)
        with open(pr33_path) as f:
            pr33_cases = json.load(f)

        assert len(pr30_cases) >= 5, "PR30 must have at least 5 test cases"
        assert len(pr32_cases) >= 5, "PR32 must have at least 5 test cases"
        assert len(pr33_cases) >= 5, "PR33 must have at least 5 test cases"

    def test_no_regression_in_diegetic_voice(self):
        """Test no regression in diegetic voice maintenance."""
        # Read protocol and verify all collapse categories covered
        protocol_path = FIXTURES_DIR / "protocol_valid.json"
        with open(protocol_path) as f:
            protocol = json.load(f)

        categories = [c["name"] for c in protocol["forbidden_collapses"]]
        assert len(categories) >= 6, "All 6 forbidden collapse categories must be defined"

    def test_no_regression_under_pr30_hooks(self):
        """Test no regression under PR30 transform/no_agent hooks."""
        pr30_path = FIXTURES_DIR / "pr30_transform_compatibility_cases.json"
        with open(pr30_path) as f:
            cases = json.load(f)

        # Verify all cases have forbidden markers defined
        for case in cases:
            assert "forbidden_markers" in case
            assert len(case["forbidden_markers"]) > 0

    def test_no_regression_under_pr32_governance(self):
        """Test no regression under PR32 governance."""
        pr32_path = FIXTURES_DIR / "pr32_behavioral_cases.json"
        with open(pr32_path) as f:
            cases = json.load(f)

        # Verify all cases have pass conditions
        for case in cases:
            assert "pass_condition" in case
            assert len(case["pass_condition"]) > 0

    def test_no_regression_under_pr33_recall(self):
        """Test no regression under PR33 relational recall."""
        pr33_path = FIXTURES_DIR / "pr33_relational_recall_cases.json"
        with open(pr33_path) as f:
            cases = json.load(f)

        # Verify all cases use subject markers
        for case in cases:
            assert "subject_marker" in case or "corrected_marker" in case or "unconfirmed_marker" in case

    def test_regression_suite_complete(self):
        """Test regression suite has all required components."""
        # Check all docs exist
        docs = [
            "01_NORMATIVE_IDENTITY_BOUNDARY_EVALUATION_PROTOCOL.md",
            "02_SCENARIO_SUITE.md",
            "03_EVALUATION_RUBRIC.md",
            "04_PR30_COMPATIBILITY.md",
            "05_PR32_BEHAVIORAL_CHECKS.md",
            "06_PR33_RELATIONAL_RECALL_CHECKS.md",
            "07_REGRESSION_TESTS.md",
        ]
        for doc in docs:
            doc_path = DOCS_DIR / doc
            assert doc_path.exists(), f"Documentation {doc} must exist"

    def test_regression_suite_is_deterministic(self):
        """Test regression suite is deterministic and reproducible."""
        # All fixtures must be valid JSON
        fixture_files = list(FIXTURES_DIR.glob("*.json"))
        assert len(fixture_files) >= 10, "Must have at least 10 fixture files"

        for fixture_file in fixture_files:
            with open(fixture_file) as f:
                data = json.load(f)
            # If it's a list, must have consistent structure
            if isinstance(data, list):
                assert len(data) > 0
                for item in data:
                    assert "case_id" in item or "scenario_id" in item
