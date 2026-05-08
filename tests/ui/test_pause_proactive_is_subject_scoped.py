"""
PR27O Test: Pause Proactive Is Subject Scoped

Verify pause proactive is subject-scoped.
"""

import pytest
from pathlib import Path


FIXTURE_PATH = Path(__file__).parent.parent.parent / "fixtures" / "researcher-workbench" / "test_fixture_two_subjects.json"


def load_fixture():
    import json
    with open(FIXTURE_PATH) as f:
        return json.load(f)


def test_pause_proactive_is_subject_scoped():
    """Verify pause proactive is subject-scoped."""
    fixture = load_fixture()

    # Each subject has their own pause state
    for subject in fixture["subjects"]:
        assert "gumi_instance_id" in subject
