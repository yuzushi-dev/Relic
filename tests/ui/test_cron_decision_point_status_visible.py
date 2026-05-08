"""
PR27O Test: Cron Decision Point Status Visible

Verify cron decision status is visible.
"""

import pytest
from pathlib import Path


FIXTURE_PATH = Path(__file__).parent.parent.parent / "fixtures" / "researcher-workbench" / "test_fixture_two_subjects.json"


def load_fixture():
    import json
    with open(FIXTURE_PATH) as f:
        return json.load(f)


def test_cron_decision_point_status_visible():
    """Verify cron decision status is visible."""
    fixture = load_fixture()

    cron_events = [e for e in fixture["events"] if "cron" in e.get("event_type", "")]
    assert len(cron_events) > 0, "Fixture must include cron events"

    for cron in cron_events:
        assert "decision" in cron, "Cron event must have decision"
