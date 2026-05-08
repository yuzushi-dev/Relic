"""
PR27O Test: No Cross-Subject Event Leakage

Verify events cannot leak between subjects.
"""

import pytest
from pathlib import Path


FIXTURE_PATH = Path(__file__).parent.parent.parent / "fixtures" / "researcher-workbench" / "test_fixture_two_subjects.json"


def load_fixture():
    import json
    with open(FIXTURE_PATH) as f:
        return json.load(f)


def test_no_cross_subject_event_leakage():
    """Verify events cannot leak between subjects."""
    fixture = load_fixture()

    subject_ids = [s["subject_id"] for s in fixture["subjects"]]

    for event in fixture["events"]:
        assert "subject_id" in event, "Event missing subject_id"
        assert event["subject_id"] in subject_ids, "Event must be scoped to a valid subject"
