"""
PR27O Test: Event Ontological Class Required

Verify every event has an ontological class.
"""

import pytest
from pathlib import Path


FIXTURE_PATH = Path(__file__).parent.parent.parent / "fixtures" / "researcher-workbench" / "test_fixture_two_subjects.json"


def load_fixture():
    import json
    with open(FIXTURE_PATH) as f:
        return json.load(f)


def test_event_ontological_class_required():
    """Verify every event has an ontological class."""
    fixture = load_fixture()

    for event in fixture["events"]:
        assert "ontological_class" in event, f"Event {event.get('event_id')} missing ontological_class"
