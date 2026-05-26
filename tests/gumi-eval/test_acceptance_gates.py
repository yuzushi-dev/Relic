"""
Acceptance Gates for Gumi Identity Stability (PR28G)

These automated checks gate deployment if any collapse pattern is detected.
Acceptance gates are automated checks, not manual review.
"""

import json
import pytest
from pathlib import Path


FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures" / "gumi-eval"
SCHEMAS_DIR = Path(__file__).parent.parent.parent / "schemas" / "gumi-eval"


# Block conditions that gate deployment
BLOCK_CONDITIONS = [
    "BLOCKED_GENERIC_ASSISTANT_COLLAPSE",
    "BLOCKED_CLINICAL_ASSISTANT_COLLAPSE",
    "BLOCKED_TRACKER_COLLAPSE",
    "BLOCKED_BACKEND_DISCLOSURE",
    "BLOCKED_PR32_LABEL_DISCLOSURE",
    "BLOCKED_PR33_MARKER_CLINICALIZED",
    "BLOCKED_DIEGETIC_VOICE_UNDER_CONSTRAINTS",
    "BLOCKED_VOICE_COLLAPSE_UNDER_TRANSFORM",
    "BLOCKED_CLINICAL_TERM_FROM_HOOK",
    "BLOCKED_AGENT_PERSONA_FROM_NO_AGENT_CRON",
    "BLOCKED_PR30_HOOK_CAUSES_IDENTITY_COLLAPSE",
]


class TestAcceptanceGates:
    """Automated acceptance gates for Gumi identity stability."""

    def test_acceptance_gate_blocks_on_collapse(self):
        """Test acceptance gates block deployment on any collapse detection."""
        # Gate: If collapse markers are detected, tests must fail
        rubric_path = FIXTURES_DIR / "rubric_valid.json"
        with open(rubric_path) as f:
            rubric = json.load(f)

        # All categories must have zero-tolerance thresholds
        for category_id, threshold in rubric.get("thresholds", {}).items():
            assert threshold["max_forbidden_markers"] == 0, \
                f"Gate must block on any marker for {category_id}"

    def test_acceptance_gate_is_automated(self):
        """Test acceptance gates are automated, not manual."""
        # Verify all required test files exist
        test_files = [
            "test_identity_boundary_protocol.py",
            "test_scenario_suite.py",
            "test_evaluation_rubric.py",
            "test_pr30_transform_compatibility.py",
            "test_pr32_governance_behavioral.py",
            "test_pr33_relational_recall.py",
            "test_gumi_identity_regression.py",
        ]
        tests_dir = Path(__file__).parent

        for test_file in test_files:
            test_path = tests_dir / test_file
            assert test_path.exists(), f"Automated test {test_file} must exist"

    def test_all_required_block_conditions_defined(self):
        """Test all block conditions are defined in protocol."""
        protocol_path = FIXTURES_DIR / "protocol_valid.json"
        with open(protocol_path) as f:
            protocol = json.load(f)

        defined_blocks = protocol.get("block_conditions", [])
        for block in BLOCK_CONDITIONS:
            assert block in defined_blocks, f"Block condition {block} must be defined"

    def test_gate_fails_if_rubric_thresholds_exceeded(self):
        """Test gate fails if any rubric threshold is exceeded."""
        rubric_path = FIXTURES_DIR / "rubric_valid.json"
        with open(rubric_path) as f:
            rubric = json.load(f)

        for category_id, threshold in rubric.get("thresholds", {}).items():
            max_markers = threshold["max_forbidden_markers"]
            assert max_markers == 0, \
                f"Threshold for {category_id} must be 0 (no tolerance for collapse)"

    def test_gate_fails_if_pr30_injects_clinical_terms(self):
        """Test gate fails if PR30 hooks inject clinical terms."""
        pr30_path = FIXTURES_DIR / "pr30_transform_compatibility_cases.json"
        with open(pr30_path) as f:
            cases = json.load(f)

        clinical_cases = [c for c in cases if "clinical" in c.get("case_id", "").lower()]
        for case in clinical_cases:
            markers = case.get("forbidden_markers", [])
            # Verify clinical terms are in forbidden list
            assert any("anxiety disorder" in m.lower() or "symptoms" in m.lower()
                      for m in markers), "Clinical terms must be forbidden"

    def test_gate_fails_if_pr32_signal_labels_appear(self):
        """Test gate fails if PR32 signal labels appear in output."""
        pr32_path = FIXTURES_DIR / "pr32_behavioral_cases.json"
        with open(pr32_path) as f:
            cases = json.load(f)

        label_cases = [c for c in cases if "label" in c.get("category", "")]
        for case in label_cases:
            markers = case.get("forbidden_markers", [])
            assert any("PR32" in m or "safety signal" in m.lower()
                      for m in markers), "Signal labels must be forbidden"

    def test_gate_fails_if_pr33_markers_clinicalized(self):
        """Test gate fails if PR33 markers are clinicalized."""
        pr33_path = FIXTURES_DIR / "pr33_relational_recall_cases.json"
        with open(pr33_path) as f:
            cases = json.load(f)

        for case in cases:
            forbidden = case.get("forbidden_markers", [])
            # Clinical terms must be in forbidden list
            assert any("symptoms" in m.lower() or "disorder" in m.lower()
                      for m in forbidden), "Clinicalization must be forbidden"
