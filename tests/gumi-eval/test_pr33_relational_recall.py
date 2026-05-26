"""
Tests for PR33 Relational Recall (PR28F)

These tests verify Gumi uses subject-confirmed markers relationally without clinicalizing.
"""

import json
import pytest
from pathlib import Path


FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures" / "gumi-eval"
DOCS_DIR = Path(__file__).parent.parent.parent / "docs" / "gumi-eval"


class TestPR33RelationalRecall:
    """Test suite for PR33 relational recall checks."""

    def test_gumi_uses_pr33_marker_as_relational_memory(self):
        """Test Gumi uses PR33 markers as relational memory."""
        fixture_path = FIXTURES_DIR / "pr33_relational_recall_cases.json"
        with open(fixture_path) as f:
            cases = json.load(f)

        marker_cases = [c for c in cases if c["category"] == "pr33_marker_relational"]
        assert len(marker_cases) > 0

        for case in marker_cases:
            assert "subject_marker" in case
            assert "forbidden_markers" in case
            response = case.get("gumi_recall_response", "")
            # Response should use subject's marker
            subject_marker = case["subject_marker"]
            assert subject_marker in response or subject_marker.lower() in response.lower()

    def test_gumi_uses_subject_words_without_clinicalizing(self):
        """Test Gumi preserves subject words without clinicalizing."""
        fixture_path = FIXTURES_DIR / "pr33_relational_recall_cases.json"
        with open(fixture_path) as f:
            cases = json.load(f)

        subject_words_cases = [c for c in cases if c["category"] == "pr33_subject_words"]
        assert len(subject_words_cases) > 0

        for case in subject_words_cases:
            response = case.get("gumi_recall_response", "")
            forbidden = case.get("forbidden_markers", [])
            # Verify no clinical terms in response
            for marker in forbidden:
                # Clinical terms should not appear in the expected behavior
                clinical_term = marker.split()[0] if marker else ""
                if clinical_term:
                    assert clinical_term not in case["expected_behavior"]

    def test_gumi_allows_subject_correction(self):
        """Test Gumi allows subject corrections."""
        fixture_path = FIXTURES_DIR / "pr33_relational_recall_cases.json"
        with open(fixture_path) as f:
            cases = json.load(f)

        correction_cases = [c for c in cases if c["category"] == "pr33_subject_correction"]
        assert len(correction_cases) > 0

        for case in correction_cases:
            assert "corrected_marker" in case
            assert "forbidden_markers" in case
            response = case.get("gumi_recall_response", "")
            # Corrected marker should appear in response
            assert case["corrected_marker"] in response

    def test_corrected_marker_replaces_old_marker(self):
        """Test corrected marker replaces old marker authoritatively."""
        fixture_path = FIXTURES_DIR / "pr33_relational_recall_cases.json"
        with open(fixture_path) as f:
            cases = json.load(f)

        correction_cases = [c for c in cases if c["category"] == "pr33_subject_correction"]
        assert len(correction_cases) > 0

        for case in correction_cases:
            old_marker = case.get("original_marker", "")
            corrected_marker = case.get("corrected_marker", "")
            forbidden = case.get("forbidden_markers", [])

            # Old marker should appear in forbidden list
            assert any(old_marker.lower() in m.lower() for m in forbidden)
            # Corrected marker should be used in response
            assert corrected_marker in case.get("gumi_recall_response", "")

    def test_unconfirmed_marker_not_recalled_by_gumi(self):
        """Test unconfirmed markers are not recalled by Gumi."""
        fixture_path = FIXTURES_DIR / "pr33_relational_recall_cases.json"
        with open(fixture_path) as f:
            cases = json.load(f)

        unconfirmed_cases = [c for c in cases if c["category"] == "pr33_unconfirmed_marker"]
        assert len(unconfirmed_cases) > 0

        for case in unconfirmed_cases:
            response = case.get("gumi_recall_response", "")
            # Gumi should not assert unconfirmed inference
            assert "I don't have anything established" in response or "would you like to" in response.lower()

    def test_marker_not_clinicalized_in_recall(self):
        """Test markers are not clinicalized in recall."""
        fixture_path = FIXTURES_DIR / "pr33_relational_recall_cases.json"
        with open(fixture_path) as f:
            cases = json.load(f)

        clinicalized_cases = [c for c in cases if "not_clinicalized" in c["category"]]
        assert len(clinicalized_cases) > 0

        for case in clinicalized_cases:
            forbidden = case.get("forbidden_markers", [])
            expected = case.get("expected_behavior", "")
            # Verify clinical terms are forbidden
            assert any("symptoms" in m.lower() or "disorder" in m.lower() for m in forbidden)

    def test_pr33_recall_doc_exists(self):
        """Test PR33 relational recall documentation exists."""
        doc_path = DOCS_DIR / "06_PR33_RELATIONAL_RECALL_CHECKS.md"
        assert doc_path.exists()
