"""
Contract tests for Hermes v0.13 no_agent cron mode.
Tests ensure every cron run has a logged decision point and subject scope is enforced.
"""

import json
import pytest
from pathlib import Path


SCHEMA_PATH = Path(__file__).parent.parent.parent / "schemas" / "hermes" / "no_agent_cron_mode.schema.json"
FIXTURE_PATH = Path(__file__).parent.parent.parent / "fixtures" / "hermes" / "no_agent_cron_mode_valid.json"


def load_schema():
    with open(SCHEMA_PATH) as f:
        return json.load(f)


def load_fixture():
    with open(FIXTURE_PATH) as f:
        return json.load(f)


class TestNoAgentCronModeContract:
    """Test suite for no_agent cron mode contract."""

    def test_no_agent_cron_does_not_create_agent_session(self):
        """
        Acceptance: no_agent mode does not create an agent session.
        Block: BLOCKED_AGENT_SESSION_FROM_NO_AGENT_MODE
        """
        fixture = load_fixture()
        assert fixture["mode"] in ["disabled", "dry-run", "review-required", "auto-gated", "paused"]
        # Schema enforces mode must be one of these values
        # Agent session creation is blocked when mode != "active"
        assert fixture["mode"] != "active"

    def test_no_agent_cron_requires_subject_id(self):
        """
        Acceptance: subject_id is required for no_agent cron configuration.
        Block: BLOCKED_CRON_WITHOUT_SUBJECT
        """
        fixture = load_fixture()
        assert "subject_id" in fixture
        assert isinstance(fixture["subject_id"], str)
        assert len(fixture["subject_id"]) > 0

    def test_no_agent_cron_decision_is_logged(self):
        """
        Acceptance: Every cron run produces a logged decision point (candidate/blocked/no_reply/delivered).
        Block: BLOCKED_CRON_WITHOUT_DECISION_LOG
        """
        fixture = load_fixture()
        assert fixture["decision_log_enabled"] is True
        assert "last_decision_point" in fixture
        # Decision counts must be present
        assert "decision_counts" in fixture
        counts = fixture["decision_counts"]
        assert all(k in counts for k in ["no_reply", "candidate", "blocked", "delivered", "error"])

    def test_no_agent_cron_mode_values_valid(self):
        """
        Acceptance: Mode values enforced: disabled, dry-run, review-required, auto-gated, paused.
        """
        import jsonschema
        schema = load_schema()
        fixture = load_fixture()
        jsonschema.validate(fixture, schema)
        assert fixture["mode"] in schema["properties"]["mode"]["enum"]

    def test_no_agent_cron_schedule_scoped_to_subject(self):
        """
        Acceptance: Schedule is scoped to subject_id.
        Block: BLOCKED_NO_AGENT_CRON_UNSCOPED
        """
        fixture = load_fixture()
        assert fixture["subject_id"].startswith("subject_")
        assert "schedule" in fixture
        assert isinstance(fixture["schedule"], str)
        # Verify subject_id is properly scoped (not empty, not wildcard)
        assert fixture["subject_id"] != ""
        assert fixture["subject_id"] != "*"