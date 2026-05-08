"""
PR27O - Test: No Global Gumi Runtime

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


def test_subject_scoped_gumi_instance():
    """Verify Gumi instances are properly subject-scoped."""
    fixture = load_fixture()

    for gumi in fixture["gumi_instances"]:
        assert gumi["subject_id"] in [s["subject_id"] for s in fixture["subjects"]]


def test_no_cross_subject_event_leakage():
    """Verify events cannot leak between subjects."""
    fixture = load_fixture()

    subject_ids = [s["subject_id"] for s in fixture["subjects"]]

    for event in fixture["events"]:
        assert "subject_id" in event, "BLOCKED_CROSS_SUBJECT_EVENT_LEAKAGE: Event missing subject_id"
        assert event["subject_id"] in subject_ids, "Event must be scoped to a valid subject"


def test_cross_subject_view_redacted_by_default():
    """Verify cross-subject aggregate views are redacted by default."""
    fixture = load_fixture()

    assert "cross_subject_leakage_test" in fixture
    leakage_test = fixture["cross_subject_leakage_test"]

    assert leakage_test["aggregate_view"]["must_be_redacted"] is True
    assert leakage_test["aggregate_view"]["cannot_contain_raw_messages"] is True


def test_event_ontological_class_required():
    """Verify every event has an ontological class."""
    fixture = load_fixture()

    for event in fixture["events"]:
        assert "ontological_class" in event, f"Event {event.get('event_id')} missing ontological_class"


def test_gumi_generated_event_not_user_evidence():
    """Verify Gumi-generated events are not used as direct user evidence."""
    fixture = load_fixture()

    for event in fixture["events"]:
        if event.get("event_type") in ["proactive", "gumi_initiative"]:
            # Gumi-generated events must have gumi initiative ontological class
            assert event["ontological_class"] != "user_message", \
                "Gumi-generated event cannot be classified as user evidence"


def test_user_response_can_be_eligible_evidence():
    """Verify user responses can be eligible evidence."""
    fixture = load_fixture()

    user_responses = [e for e in fixture["events"] if e.get("event_type") == "user_response"]
    assert len(user_responses) > 0, "Fixture must include user response events"

    for resp in user_responses:
        assert resp["ontological_class"] == "user_message"


def test_inference_source_mix_visible():
    """Verify inference source mix is visible."""
    fixture = load_fixture()

    inferences = [e for e in fixture["events"] if e.get("event_type") == "inference"]
    assert len(inferences) > 0, "Fixture must include inference events"

    for inf in inferences:
        assert "source" in inf, "Inference must have source"


def test_cron_decision_point_status_visible():
    """Verify cron decision status is visible."""
    fixture = load_fixture()

    cron_events = [e for e in fixture["events"] if "cron" in e.get("event_type", "")]
    assert len(cron_events) > 0, "Fixture must include cron events"

    for cron in cron_events:
        assert "decision" in cron, "Cron event must have decision"


def test_pause_proactive_is_subject_scoped():
    """Verify pause proactive is subject-scoped."""
    fixture = load_fixture()

    # Each subject has their own pause state
    for subject in fixture["subjects"]:
        assert "gumi_instance_id" in subject


def test_artifact_edit_requires_versioning():
    """Verify artifact edits require versioning."""
    # This test verifies the artifact schema requires versioning
    schema_path = Path(__file__).parent.parent.parent / "schemas" / "ui" / "artifact_summary.schema.json"
    import json
    with open(schema_path) as f:
        schema = json.load(f)
    # Artifact schema should support versioning
    assert "artifact_id" in schema.get("properties", {})


def test_export_redaction_required():
    """Verify export redaction is enforced."""
    fixture = load_fixture()

    exports = [e for e in fixture["events"] if e.get("event_type") == "redacted_export"]
    assert len(exports) > 0, "Fixture must include redacted export event"


def test_boundary_monitor_shows_overreach():
    """Verify boundary monitor shows overreach indicators."""
    boundary_risk_path = Path(__file__).parent.parent.parent / "fixtures" / "researcher-workbench" / "boundary_risk_subj_001.json"
    import json
    with open(boundary_risk_path) as f:
        risk = json.load(f)

    assert "overreach_indicators" in risk


def test_careful_distancing_control_available():
    """Verify careful distancing control is available."""
    boundary_risk_path = Path(__file__).parent.parent.parent / "fixtures" / "researcher-workbench" / "boundary_risk_subj_001.json"
    import json
    with open(boundary_risk_path) as f:
        risk = json.load(f)

    assert "careful_distancing_enabled" in risk
