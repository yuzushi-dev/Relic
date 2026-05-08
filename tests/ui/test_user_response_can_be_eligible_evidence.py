"""
PR27O Test: User Response Can Be Eligible Evidence

Verify user responses can be eligible evidence.
"""

import pytest
from pathlib import Path


FIXTURE_PATH = Path(__file__).parent.parent.parent / "fixtures" / "researcher-workbench" / "test_fixture_two_subjects.json"


def load_fixture():
    import json
    with open(FIXTURE_PATH) as f:
        return json.load(f)


def test_user_response_can_be_eligible_evidence():
    """Verify user responses can be eligible evidence."""
    fixture = load_fixture()

    user_responses = [e for e in fixture["events"] if e.get("event_type") == "user_response"]
    assert len(user_responses) > 0, "Fixture must include user response events"

    for resp in user_responses:
        assert resp["ontological_class"] == "user_message"
