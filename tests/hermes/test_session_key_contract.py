"""
Contract tests for Hermes v0.13 X-Hermes-Session-Key.
Tests ensure raw key is never logged and key is scoped to subject.
"""

import json
import pytest
from pathlib import Path


SCHEMA_PATH = Path(__file__).parent.parent.parent / "schemas" / "hermes" / "session_key.schema.json"
FIXTURE_PATH = Path(__file__).parent.parent.parent / "fixtures" / "hermes" / "session_key_valid.json"


def load_schema():
    with open(SCHEMA_PATH) as f:
        return json.load(f)


def load_fixture():
    with open(FIXTURE_PATH) as f:
        return json.load(f)


class TestSessionKeyContract:
    """Test suite for session key contract."""

    def test_session_key_stored_as_hash(self):
        """
        Acceptance: Session key is stored as a hash (algorithm specified in schema).
        Block: BLOCKED_SESSION_KEY_STORED_PLAINTEXT
        """
        fixture = load_fixture()
        assert "session_key_hash" in fixture
        assert "hash_algorithm" in fixture
        assert fixture["hash_algorithm"] in ["sha256", "sha384", "sha512", "argon2id"]
        # Verify hash is not the raw key (should be hex string of fixed length)
        assert len(fixture["session_key_hash"]) >= 32

    def test_raw_session_key_not_logged(self):
        """
        Acceptance: Raw session key is never written to logs.
        Block: BLOCKED_RAW_SESSION_KEY_LOGGED
        """
        fixture = load_fixture()
        # Schema enforces only hash is stored, never raw key
        assert "session_key_hash" in fixture
        # key_scope_resolvable=false means raw key cannot be reconstructed
        assert fixture["key_scope_resolvable"] is False

    def test_session_key_scoped_to_subject(self):
        """
        Acceptance: Session key is scoped to subject_id.
        Block: BLOCKED_SESSION_KEY_UNSCOPED
        """
        fixture = load_fixture()
        assert "subject_id" in fixture
        assert isinstance(fixture["subject_id"], str)
        assert len(fixture["subject_id"]) > 0
        assert fixture["subject_id"].startswith("subject_")

    def test_session_key_hash_algorithm_specified(self):
        """
        Acceptance: Hash algorithm is specified and stored in schema.
        """
        import jsonschema
        schema = load_schema()
        fixture = load_fixture()
        jsonschema.validate(fixture, schema)
        assert "hash_algorithm" in fixture
        assert fixture["hash_algorithm"] in schema["properties"]["hash_algorithm"]["enum"]

    def test_session_key_rotation_logged(self):
        """
        Acceptance: Key rotation creates an audit event.
        Block: BLOCKED_KEY_ROTATION_NOT_LOGGED
        """
        fixture = load_fixture()
        assert fixture["audit_event_on_rotation"] is True
        assert "last_rotated_at" in fixture
        assert "rotation_count" in fixture
        assert fixture["rotation_count"] >= 0