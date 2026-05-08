"""
PR27O Test: Gumi Generated Event Not User Evidence

Verify Gumi-generated events are not used as direct user evidence.
"""

import pytest
from pathlib import Path


FIXTURE_PATH = Path(__file__).parent.parent.parent / "fixtures" / "researcher-workbench" / "test_fixture_two_subjects.json"


def load_fixture():
    import json
    with open(FIXTURE_PATH) as f:
        return json.load(f)


def test_gumi_generated_event_not_user_evidence():
    """Verify Gumi-generated events are not used as direct user evidence."""
    fixture = load_fixture()

    for event in fixture["events"]:
        if event.get("event_type") in ["proactive", "gumi_initiative"]:
            assert event["ontological_class"] != "user_message", \
                "Gumi-generated event cannot be classified as user evidence"
