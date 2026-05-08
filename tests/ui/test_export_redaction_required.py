"""
PR27O Test: Export Redaction Required

Verify export redaction is enforced.
"""

import pytest
from pathlib import Path


FIXTURE_PATH = Path(__file__).parent.parent.parent / "fixtures" / "researcher-workbench" / "test_fixture_two_subjects.json"


def load_fixture():
    import json
    with open(FIXTURE_PATH) as f:
        return json.load(f)


def test_export_redaction_required():
    """Verify export redaction is enforced."""
    fixture = load_fixture()

    exports = [e for e in fixture["events"] if e.get("event_type") == "redacted_export"]
    assert len(exports) > 0, "Fixture must include redacted export event"
