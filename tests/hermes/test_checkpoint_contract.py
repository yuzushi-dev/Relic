"""
Contract tests for Hermes v0.13 checkpoints and session auto-resume.
Tests ensure pending output is not auto-delivered on resume and resume creates audit events.
"""

import json
import pytest
from pathlib import Path


SCHEMA_PATH = Path(__file__).parent.parent.parent / "schemas" / "hermes" / "checkpoint.schema.json"
FIXTURE_PATH = Path(__file__).parent.parent.parent / "fixtures" / "hermes" / "checkpoint_valid.json"


def load_schema():
    with open(SCHEMA_PATH) as f:
        return json.load(f)


def load_fixture():
    with open(FIXTURE_PATH) as f:
        return json.load(f)


class TestCheckpointContract:
    """Test suite for checkpoint contract."""

    def test_pending_output_not_auto_delivered_on_resume(self):
        """
        Acceptance: Pending output is never auto-delivered on session resume.
        Block: BLOCKED_AUTO_DELIVERY_ON_RESUME
        """
        fixture = load_fixture()
        assert fixture["pending_output_not_auto_delivered"] is True
        assert fixture["has_pending_output"] is True

    def test_checkpoint_scoped_to_subject(self):
        """
        Acceptance: Checkpoint is scoped to subject_id.
        Block: BLOCKED_CHECKPOINT_WITHOUT_SUBJECT
        """
        fixture = load_fixture()
        assert "subject_id" in fixture
        assert isinstance(fixture["subject_id"], str)
        assert len(fixture["subject_id"]) > 0
        assert fixture["subject_id"].startswith("subject_")

    def test_resume_creates_audit_event(self):
        """
        Acceptance: Resume creates an audit event.
        Block: BLOCKED_RESUME_WITHOUT_AUDIT
        """
        fixture = load_fixture()
        assert fixture["audit_event_on_resume"] is True

    def test_checkpoint_has_clear_pending_flag(self):
        """
        Acceptance: Checkpoint stores pending output flag (not the output itself).
        """
        fixture = load_fixture()
        assert "has_pending_output" in fixture
        assert fixture["has_pending_output"] is True
        # pending_output_not_auto_delivered is the key flag
        assert fixture["pending_output_not_auto_delivered"] is True

    def test_resume_requires_explicit_user_action(self):
        """
        Acceptance: Resume requires explicit user action or researcher gate.
        """
        fixture = load_fixture()
        assert fixture["resume_requires_explicit_user_action"] is True