"""
PR27O Test: Inference Source Mix Visible

Verify inference source mix is visible.
"""

import pytest
from pathlib import Path


FIXTURE_PATH = Path(__file__).parent.parent.parent / "fixtures" / "researcher-workbench" / "test_fixture_two_subjects.json"


def load_fixture():
    import json
    with open(FIXTURE_PATH) as f:
        return json.load(f)


def test_inference_source_mix_visible():
    """Verify inference source mix is visible."""
    fixture = load_fixture()

    inferences = [e for e in fixture["events"] if e.get("event_type") == "inference"]
    assert len(inferences) > 0, "Fixture must include inference events"

    for inf in inferences:
        assert "source" in inf, "Inference must have source"
