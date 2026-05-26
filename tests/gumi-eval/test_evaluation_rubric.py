"""
Tests for the Gumi Evaluation Rubric (PR28C)

These tests validate the evaluation rubric schema and scoring format.
"""

import json
import pytest
from pathlib import Path


FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures" / "gumi-eval"
SCHEMAS_DIR = Path(__file__).parent.parent.parent / "schemas" / "gumi-eval"
DOCS_DIR = Path(__file__).parent.parent.parent / "docs" / "gumi-eval"


class TestEvaluationRubric:
    """Test suite for evaluation rubric."""

    def test_rubric_schema_valid(self):
        """Test that rubric_valid.json conforms to evaluation_rubric.schema.json."""
        rubric_path = FIXTURES_DIR / "rubric_valid.json"
        with open(rubric_path) as f:
            data = json.load(f)

        assert "version" in data
        assert "collapse_categories" in data
        assert len(data["collapse_categories"]) == 6

    def test_result_schema_valid(self):
        """Test that result_sample.json conforms to evaluation_result.schema.json."""
        result_path = FIXTURES_DIR / "result_sample.json"
        with open(result_path) as f:
            data = json.load(f)

        assert "scenario_id" in data
        assert "category" in data
        assert "pass" in data
        assert "failure_markers" in data
        assert "confidence" in data

    def test_rubric_covers_all_collapse_categories(self):
        """Test rubric covers all 6 collapse categories."""
        rubric_path = FIXTURES_DIR / "rubric_valid.json"
        with open(rubric_path) as f:
            data = json.load(f)

        categories = [c["category_id"] for c in data["collapse_categories"]]
        assert "generic_assistant_collapse" in categories
        assert "clinical_assistant_collapse" in categories
        assert "mood_tracker_collapse" in categories
        assert "backend_disclosure" in categories
        assert "pr32_label_disclosure" in categories
        assert "pr33_marker_clinicalization" in categories

    def test_rubric_has_pass_fail_per_category(self):
        """Test rubric defines pass/fail conditions for each category."""
        rubric_path = FIXTURES_DIR / "rubric_valid.json"
        with open(rubric_path) as f:
            data = json.load(f)

        for category in data["collapse_categories"]:
            assert "pass_condition" in category
            assert "fail_condition" in category
            assert len(category["pass_condition"]) > 0
            assert len(category["fail_condition"]) > 0

    def test_rubric_result_is_machine_readable(self):
        """Test that evaluation result has machine-readable fields."""
        result_path = FIXTURES_DIR / "result_sample.json"
        with open(result_path) as f:
            data = json.load(f)

        # Verify all required fields are present with correct types
        assert isinstance(data["scenario_id"], str)
        assert isinstance(data["category"], str)
        assert isinstance(data["pass"], bool)
        assert isinstance(data["failure_markers"], list)
        assert isinstance(data["confidence"], (int, float))
        assert 0 <= data["confidence"] <= 1

    def test_rubric_scores_identity_stability(self):
        """Test that rubric defines thresholds for pass/fail per collapse type."""
        rubric_path = FIXTURES_DIR / "rubric_valid.json"
        with open(rubric_path) as f:
            data = json.load(f)

        assert "thresholds" in data
        for category_id in ["generic_assistant_collapse", "clinical_assistant_collapse",
                            "mood_tracker_collapse", "backend_disclosure",
                            "pr32_label_disclosure", "pr33_marker_clinicalization"]:
            assert category_id in data["thresholds"]
            assert data["thresholds"][category_id]["max_forbidden_markers"] == 0

    def test_rubric_doc_exists(self):
        """Test that rubric documentation exists."""
        doc_path = DOCS_DIR / "03_EVALUATION_RUBRIC.md"
        assert doc_path.exists()
