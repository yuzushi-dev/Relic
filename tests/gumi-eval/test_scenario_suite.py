"""
Tests for the Gumi Scenario Suite (PR28B)

These tests validate that all scenario fixtures are properly formed
and cover all required collapse categories.
"""

import json
import pytest
from pathlib import Path


FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "gumi-eval"
SCHEMAS_DIR = Path(__file__).parent.parent / "schemas" / "gumi-eval"


SCENARIO_FILES = [
    "scenario_identity_collapse.json",
    "scenario_clinical_collapse.json",
    "scenario_tracker_collapse.json",
    "scenario_backend_disclosure.json",
    "scenario_pr32_label_disclosure.json",
    "scenario_pr33_relational_recall.json",
]

CATEGORIES = [
    "identity_collapse",
    "clinical_collapse",
    "tracker_collapse",
    "backend_disclosure",
    "pr32_label_disclosure",
    "pr33_relational_recall",
]


class TestScenarioSuite:
    """Test suite for scenario fixtures."""

    def test_scenario_fixtures_valid_json(self):
        """Test that all scenario fixtures are valid JSON."""
        for filename in SCENARIO_FILES:
            fixture_path = FIXTURES_DIR / filename
            assert fixture_path.exists(), f"Fixture {filename} must exist"
            with open(fixture_path) as f:
                data = json.load(f)
            assert isinstance(data, dict), f"{filename} must be a JSON object"

    def test_each_scenario_has_prompt_and_expected_behavior(self):
        """Test that each scenario has required fields."""
        for filename in SCENARIO_FILES:
            fixture_path = FIXTURES_DIR / filename
            with open(fixture_path) as f:
                data = json.load(f)
            assert "prompt" in data, f"{filename} must have prompt"
            assert "expected_behavior_markers" in data, f"{filename} must have expected_behavior_markers"

    def test_scenario_covers_all_collapse_categories(self):
        """Test that all 6 collapse categories are covered."""
        covered_categories = set()
        for filename in SCENARIO_FILES:
            fixture_path = FIXTURES_DIR / filename
            with open(fixture_path) as f:
                data = json.load(f)
            if "category" in data:
                covered_categories.add(data["category"])

        for category in CATEGORIES:
            assert category in covered_categories, f"Category {category} must be covered"

    def test_scenario_identity_collapse_has_forbidden_and_expected(self):
        """Test identity collapse scenario has both forbidden and expected markers."""
        fixture_path = FIXTURES_DIR / "scenario_identity_collapse.json"
        with open(fixture_path) as f:
            data = json.load(f)
        assert len(data.get("forbidden_behavior_markers", [])) > 0
        assert len(data.get("expected_behavior_markers", [])) > 0

    def test_scenario_clinical_collapse_has_forbidden_and_expected(self):
        """Test clinical collapse scenario has both forbidden and expected markers."""
        fixture_path = FIXTURES_DIR / "scenario_clinical_collapse.json"
        with open(fixture_path) as f:
            data = json.load(f)
        assert len(data.get("forbidden_behavior_markers", [])) > 0
        assert len(data.get("expected_behavior_markers", [])) > 0

    def test_scenario_tracker_collapse_has_forbidden_and_expected(self):
        """Test tracker collapse scenario has both forbidden and expected markers."""
        fixture_path = FIXTURES_DIR / "scenario_tracker_collapse.json"
        with open(fixture_path) as f:
            data = json.load(f)
        assert len(data.get("forbidden_behavior_markers", [])) > 0
        assert len(data.get("expected_behavior_markers", [])) > 0

    def test_scenario_backend_disclosure_has_forbidden_and_expected(self):
        """Test backend disclosure scenario has both forbidden and expected markers."""
        fixture_path = FIXTURES_DIR / "scenario_backend_disclosure.json"
        with open(fixture_path) as f:
            data = json.load(f)
        assert len(data.get("forbidden_behavior_markers", [])) > 0
        assert len(data.get("expected_behavior_markers", [])) > 0

    def test_scenario_pr32_has_no_signal_label_in_gumi_output(self):
        """Test PR32 scenario forbids signal labels."""
        fixture_path = FIXTURES_DIR / "scenario_pr32_label_disclosure.json"
        with open(fixture_path) as f:
            data = json.load(f)
        forbidden = data.get("forbidden_behavior_markers", [])
        assert any("signal" in marker.lower() for marker in forbidden), "PR32 scenario must forbid signal labels"

    def test_scenario_pr33_has_subject_confirmed_marker_only(self):
        """Test PR33 scenario preserves subject's wording."""
        fixture_path = FIXTURES_DIR / "scenario_pr33_relational_recall.json"
        with open(fixture_path) as f:
            data = json.load(f)
        expected = data.get("expected_behavior_markers", [])
        assert any("hum" in marker.lower() for marker in expected), "PR33 scenario must reference subject's 'hum' marker"

    def test_all_scenarios_have_scenario_id(self):
        """Test all scenarios have scenario_id."""
        for filename in SCENARIO_FILES:
            fixture_path = FIXTURES_DIR / filename
            with open(fixture_path) as f:
                data = json.load(f)
            assert "scenario_id" in data, f"{filename} must have scenario_id"

    def test_all_scenarios_have_test_logic(self):
        """Test all scenarios have test_logic."""
        for filename in SCENARIO_FILES:
            fixture_path = FIXTURES_DIR / filename
            with open(fixture_path) as f:
                data = json.load(f)
            assert "test_logic" in data, f"{filename} must have test_logic"
