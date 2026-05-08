"""
PR27O Test: Cross-Subject View Redacted By Default

Verify cross-subject aggregate views are redacted by default.
"""

import pytest
from pathlib import Path


FIXTURE_PATH = Path(__file__).parent.parent.parent / "fixtures" / "researcher-workbench" / "test_fixture_two_subjects.json"


def load_fixture():
    import json
    with open(FIXTURE_PATH) as f:
        return json.load(f)


def test_cross_subject_view_redacted_by_default():
    """Verify cross-subject aggregate views are redacted by default."""
    fixture = load_fixture()

    assert "cross_subject_leakage_test" in fixture
    leakage_test = fixture["cross_subject_leakage_test"]

    assert leakage_test["aggregate_view"]["must_be_redacted"] is True
    assert leakage_test["aggregate_view"]["cannot_contain_raw_messages"] is True
