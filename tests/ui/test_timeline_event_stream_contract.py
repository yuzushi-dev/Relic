"""
PR27F, Timeline and Event Stream Viewer
Contract tests for event_stream_subj_001.json fixture.

Verifies:
- Every event has subject_id
- Every event has ontological_class (one of 10 required values)
- Timeline defaults to subject scope (subject_id consistent)
- Event detail fields present (policy_snapshot, source_refs, eligibility)
- Block conditions: no event without subject_id or ontological_class
"""

import json
import pathlib
import pytest

FIXTURE_PATH = pathlib.Path(__file__).parents[2] / "fixtures" / "researcher-workbench" / "event_stream_subj_001.json"

VALID_ONTOLOGICAL_CLASSES = {
    "empirical_user_interaction",
    "active_elicitation",
    "proactive_support",
    "gumi_diegetic_event",
    "expressive_media",
    "user_response_to_gumi",
    "system_inference",
    "correction",
    "governance_decision",
    "system_maintenance",
}

VALID_DECISIONS = {"delivered", "blocked", "no_reply", "candidate"}
VALID_RISK_LEVELS = {"none", "low", "medium", "high"}
VALID_RAW_AVAILABILITY = {"local-only", "redacted", "unavailable"}
VALID_INITIATORS = {"user", "gumi", "system", "researcher"}


@pytest.fixture(scope="module")
def fixture_data():
    with open(FIXTURE_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def events(fixture_data):
    return fixture_data["events"]


def test_fixture_loads(fixture_data):
    assert fixture_data is not None


def test_fixture_has_subject_id(fixture_data):
    assert "subject_id" in fixture_data
    assert fixture_data["subject_id"]


def test_fixture_has_events(events):
    assert len(events) > 0, "Fixture must contain at least one event"


def test_every_event_has_subject_id(events):
    """BLOCKED_EVENT_WITHOUT_SUBJECT: every event must have subject_id."""
    for event in events:
        assert "subject_id" in event, f"Event {event.get('event_id')} missing subject_id"
        assert event["subject_id"], f"Event {event.get('event_id')} has empty subject_id"


def test_every_event_has_ontological_class(events):
    """BLOCKED_EVENT_WITHOUT_ONTOLOGICAL_CLASS: every event must have valid ontological_class."""
    for event in events:
        assert "ontological_class" in event, f"Event {event.get('event_id')} missing ontological_class"
        assert event["ontological_class"] in VALID_ONTOLOGICAL_CLASSES, (
            f"Event {event.get('event_id')} has invalid ontological_class: {event['ontological_class']}"
        )


def test_timeline_subject_scope(fixture_data, events):
    """Timeline defaults to subject scope: all events share the fixture's subject_id."""
    fixture_subject = fixture_data["subject_id"]
    for event in events:
        assert event["subject_id"] == fixture_subject, (
            f"Event {event.get('event_id')} subject_id {event['subject_id']} "
            f"does not match fixture subject {fixture_subject}, BLOCKED_CROSS_SUBJECT_RAW_TIMELINE"
        )


def test_every_event_has_gumi_instance_id(events):
    for event in events:
        assert "gumi_instance_id" in event
        assert event["gumi_instance_id"]


def test_every_event_has_hermes_profile_id(events):
    for event in events:
        assert "hermes_profile_id" in event
        assert event["hermes_profile_id"]


def test_every_event_has_valid_decision(events):
    for event in events:
        assert "decision" in event
        assert event["decision"] in VALID_DECISIONS, (
            f"Event {event.get('event_id')} has invalid decision: {event['decision']}"
        )


def test_every_event_has_policy_snapshot(events):
    """Event detail must show policy snapshot."""
    for event in events:
        assert "policy_snapshot" in event, f"Event {event.get('event_id')} missing policy_snapshot"
        assert isinstance(event["policy_snapshot"], dict)


def test_every_event_has_source_refs(events):
    """Event detail must show source refs."""
    for event in events:
        assert "source_refs" in event, f"Event {event.get('event_id')} missing source_refs"
        assert isinstance(event["source_refs"], list)


def test_every_event_has_eligibility_fields(events):
    """BLOCKED_EVENT_ELIGIBILITY_MISSING: eligibility fields must be present."""
    for event in events:
        assert "eligible_for_user_model" in event, (
            f"Event {event.get('event_id')} missing eligible_for_user_model"
        )
        assert "eligible_for_experience_analysis" in event, (
            f"Event {event.get('event_id')} missing eligible_for_experience_analysis"
        )
        assert isinstance(event["eligible_for_user_model"], bool)
        assert isinstance(event["eligible_for_experience_analysis"], bool)


def test_every_event_has_raw_content_availability(events):
    for event in events:
        assert "raw_content_availability" in event
        assert event["raw_content_availability"] in VALID_RAW_AVAILABILITY


def test_every_event_has_risk_level(events):
    for event in events:
        assert "risk_level" in event
        assert event["risk_level"] in VALID_RISK_LEVELS


def test_every_event_has_initiator(events):
    for event in events:
        assert "initiator" in event
        assert event["initiator"] in VALID_INITIATORS


def test_every_event_has_boolean_flags(events):
    boolean_flags = ["delivered", "has_user_response", "has_correction", "has_boundary_risk", "has_media"]
    for event in events:
        for flag in boolean_flags:
            assert flag in event, f"Event {event.get('event_id')} missing {flag}"
            assert isinstance(event[flag], bool), f"Event {event.get('event_id')} {flag} must be bool"


def test_content_preview_length(events):
    for event in events:
        if event.get("content_preview") is not None:
            assert len(event["content_preview"]) <= 80, (
                f"Event {event.get('event_id')} content_preview exceeds 80 chars"
            )


def test_related_ids_are_lists(events):
    for event in events:
        assert isinstance(event.get("related_inference_ids", []), list)
        assert isinstance(event.get("related_correction_ids", []), list)


def test_at_least_one_delivered_event(events):
    delivered = [e for e in events if e["decision"] == "delivered"]
    assert len(delivered) > 0, "Fixture must contain at least one delivered event"


def test_at_least_one_blocked_event(events):
    blocked = [e for e in events if e["decision"] == "blocked"]
    assert len(blocked) > 0, "Fixture must contain at least one blocked event"
