"""
PR27O Test: Subject Scoped Gumi Instance

Verify Gumi instances are properly subject-scoped.
"""

import pytest
from pathlib import Path


FIXTURE_PATH = Path(__file__).parent.parent.parent / "fixtures" / "researcher-workbench" / "test_fixture_two_subjects.json"


def load_fixture():
    import json
    with open(FIXTURE_PATH) as f:
        return json.load(f)


def test_subject_scoped_gumi_instance():
    """Verify Gumi instances are properly subject-scoped."""
    fixture = load_fixture()

    subject_ids = [s["subject_id"] for s in fixture["subjects"]]

    for gumi in fixture["gumi_instances"]:
        assert "subject_id" in gumi
        assert gumi["subject_id"] in subject_ids
