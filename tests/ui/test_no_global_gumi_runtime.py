"""
PR27O Test: No Global Gumi Runtime

Test suite fails if Gumi is modeled as global singleton.
"""

import pytest
from pathlib import Path


FIXTURE_PATH = Path(__file__).parent.parent.parent / "fixtures" / "researcher-workbench" / "test_fixture_two_subjects.json"


def load_fixture():
    import json
    with open(FIXTURE_PATH) as f:
        return json.load(f)


def test_no_global_gumi_runtime():
    """Gumi instances must be subject-scoped, not a global singleton."""
    fixture = load_fixture()

    # Each Gumi instance must have a subject_id
    for gumi in fixture["gumi_instances"]:
        assert "subject_id" in gumi, "BLOCKED_GLOBAL_GUMI_RUNTIME: Gumi instance missing subject_id"
        assert gumi["subject_id"] is not None

    # There must be multiple Gumi instances for multiple subjects
    gumi_subject_ids = [g["subject_id"] for g in fixture["gumi_instances"]]
    assert len(set(gumi_subject_ids)) > 1, "Gumi must not be a global singleton"
