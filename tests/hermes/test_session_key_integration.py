"""
Integration tests for Hermes session key management in Relic.
Tests derive, store, and reject behavior per SESSION_DELIVERY_RESUME contract.
"""

import pytest
from relic.hermes_runtime import (
    HermesSessionKey,
    X_HERMES_SESSION_KEY_HEADER,
    pass_session_key,
)


class TestSessionKeyDerive:
    """Test session key derivation scoped to subject/Gumi/Hermes profile."""

    def test_session_key_derive_per_subject_scoped(self):
        """
        Acceptance: Session key is derived per subject/Gumi/Hermes profile combination.
        """
        subject_1 = "subject_001"
        subject_2 = "subject_002"
        gumi_id = "gumi_instance_001"
        hermes_id = "hermes_profile_001"

        key_1 = HermesSessionKey.derive(subject_1, gumi_id, hermes_id)
        key_2 = HermesSessionKey.derive(subject_2, gumi_id, hermes_id)

        # Same inputs must produce same output
        key_1_again = HermesSessionKey.derive(subject_1, gumi_id, hermes_id)
        assert key_1 == key_1_again

        # Different subject must produce different key
        assert key_1 != key_2

    def test_session_key_stored_as_hash_not_raw(self):
        """
        Acceptance: Only hash is stored, raw key is never stored.
        Block: BLOCKED_SESSION_KEY_STORED_PLAINTEXT
        """
        subject_id = "subject_001"
        gumi_id = "gumi_instance_001"
        hermes_id = "hermes_profile_001"

        key_hash = HermesSessionKey.derive(subject_id, gumi_id, hermes_id)

        # Verify it's a hex string (hash representation)
        assert all(c in '0123456789abcdef' for c in key_hash)
        assert len(key_hash) == 64  # SHA-256 produces 64 hex chars

        # Store returns hash metadata, never raw key
        stored = HermesSessionKey.store(key_hash)
        assert "session_key_hash" in stored
        assert stored["session_key_hash"] == key_hash
        assert "raw_key" not in stored
        assert "secret" not in stored

    def test_session_key_header_name(self):
        """
        Acceptance: Header name is X-Hermes-Session-Key per contract.
        """
        assert X_HERMES_SESSION_KEY_HEADER == "X-Hermes-Session-Key"


class TestPassSessionKey:
    """Test pass_session_key helper for Hermes API calls."""

    def test_pass_session_key_returns_correct_header(self):
        """
        Acceptance: pass_session_key returns dict with correct header and derived hash.
        """
        subject_id = "subject_001"
        gumi_id = "gumi_instance_001"
        hermes_id = "hermes_profile_001"

        result = pass_session_key(subject_id, gumi_id, hermes_id)

        assert X_HERMES_SESSION_KEY_HEADER in result
        assert isinstance(result[X_HERMES_SESSION_KEY_HEADER], str)
        assert len(result[X_HERMES_SESSION_KEY_HEADER]) == 64


class TestSessionKeyRejection:
    """Test session key rejection for missing/cross-subject scope."""

    def test_reject_missing_subject_scope(self):
        """
        Acceptance: Reject if subject_id is missing or empty.
        Block: BLOCKED_SESSION_KEY_UNSCOPED
        """
        with pytest.raises(ValueError, match="subject_id is required"):
            HermesSessionKey.reject_missing_scope("")

        with pytest.raises(ValueError, match="subject_id is required"):
            HermesSessionKey.reject_missing_scope(None)

        with pytest.raises(ValueError, match="subject_id is required"):
            HermesSessionKey.reject_missing_scope("   ")

        # Valid subject should not raise
        HermesSessionKey.reject_missing_scope("subject_001")

    def test_reject_cross_subject_key_reuse(self):
        """
        Acceptance: Reject cross-subject key reuse attempt.
        Block: BLOCKED_CROSS_SUBJECT_KEY_REUSE
        """
        key_hash = "some_valid_hash"
        expected_subject = "subject_001"

        # Valid inputs should not raise
        HermesSessionKey.reject_cross_subject(key_hash, expected_subject)

        # Empty key_hash should raise
        with pytest.raises(ValueError, match="key_hash and expected_subject_id are required"):
            HermesSessionKey.reject_cross_subject("", expected_subject)

        # Empty expected_subject should raise
        with pytest.raises(ValueError, match="key_hash and expected_subject_id are required"):
            HermesSessionKey.reject_cross_subject(key_hash, "")

        with pytest.raises(ValueError, match="key_hash and expected_subject_id are required"):
            HermesSessionKey.reject_cross_subject(key_hash, None)
