"""
Tests for WIRE03: Hermes client session key injection.

Every subject-scoped Relic->Hermes API call must include X-Hermes-Session-Key header.
"""

import logging
import pytest
from unittest.mock import patch

from relic.hermes_client import HermesClient, create_hermes_client, _hash_for_logging
from relic.hermes_runtime import X_HERMES_SESSION_KEY_HEADER


class TestHermesClientSessionKey:
    """Test suite for HermesClient session key handling."""

    def test_hermes_client_adds_session_key_header(self):
        """
        Acceptance: Every HermesClient.call() includes X-Hermes-Session-Key header.
        Block: BLOCKED_MISSING_SESSION_KEY_HEADER
        """
        client = HermesClient(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
        )

        with patch.object(client, "_make_request") as mock_request:
            mock_request.return_value = {"status": "ok"}
            result = client.call("POST", "/chat")

            # Verify header was injected
            mock_request.assert_called_once()
            call_kwargs = mock_request.call_args[1]
            assert "headers" in call_kwargs
            assert X_HERMES_SESSION_KEY_HEADER in call_kwargs["headers"]
            # Header value should be the session key hash (64 hex chars for sha256)
            header_value = call_kwargs["headers"][X_HERMES_SESSION_KEY_HEADER]
            assert len(header_value) == 64
            assert all(c in '0123456789abcdef' for c in header_value)

    def test_hermes_client_logs_only_hash(self):
        """
        Acceptance: Raw session key is never logged - only hash is emitted.
        Block: BLOCKED_RAW_SESSION_KEY_LOGGED
        """
        client = HermesClient(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
        )

        # Capture log output
        log_capture = []

        class LogCapture(logging.Handler):
            def emit(self, record):
                log_capture.append(self.format(record))

        handler = LogCapture()
        handler.setLevel(logging.DEBUG)
        logger = logging.getLogger("relic.hermes_client")
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        try:
            with patch.object(client, "_make_request") as mock_request:
                mock_request.return_value = {"status": "ok"}
                client.call("GET", "/status")

            # Check that raw session key hash does not appear in any log
            for log_entry in log_capture:
                # The raw 64-char hash should not appear in logs
                assert client.session_key_hash not in log_entry, \
                    f"Raw session key hash found in log: {log_entry}"
        finally:
            logger.removeHandler(handler)

    def test_hermes_client_rejects_missing_subject_scope(self):
        """
        Acceptance: HermesClient raises ValueError if subject_id is missing.
        Block: BLOCKED_SESSION_KEY_UNSCOPED
        """
        with pytest.raises(ValueError, match="subject_id is required"):
            HermesClient("", "gumi_001", "hermes_001")

        with pytest.raises(ValueError, match="subject_id is required"):
            HermesClient(None, "gumi_001", "hermes_001")

        with pytest.raises(ValueError, match="subject_id is required"):
            HermesClient("   ", "gumi_001", "hermes_001")

    def test_hermes_client_rejects_cross_subject_key(self):
        """
        Acceptance: HermesClient.validate_call_scope rejects cross-subject calls.
        Block: BLOCKED_CROSS_SUBJECT_KEY_REUSE
        """
        client = HermesClient(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
        )

        # Valid subject should pass
        client.validate_call_scope("subj_001")

        # Cross-subject should raise
        with pytest.raises(ValueError, match="Cross-subject key reuse detected"):
            client.validate_call_scope("subj_002")

        with pytest.raises(ValueError, match="Cross-subject key reuse detected"):
            client.validate_call_scope("subj_other")

    def test_hermes_client_requires_gumi_instance_id(self):
        """Gumi instance ID is required."""
        with pytest.raises(ValueError, match="gumi_instance_id is required"):
            HermesClient("subj_001", "", "hermes_001")

        with pytest.raises(ValueError, match="gumi_instance_id is required"):
            HermesClient("subj_001", None, "hermes_001")

    def test_hermes_client_requires_hermes_profile_id(self):
        """Hermes profile ID is required."""
        with pytest.raises(ValueError, match="hermes_profile_id is required"):
            HermesClient("subj_001", "gumi_001", "")

        with pytest.raises(ValueError, match="hermes_profile_id is required"):
            HermesClient("subj_001", "gumi_001", None)


class TestCreateHermesClient:
    """Test factory function for HermesClient creation."""

    def test_create_hermes_client_returns_configured_client(self):
        """Factory creates properly configured HermesClient."""
        client = create_hermes_client(
            subject_id="subj_001",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
        )

        assert isinstance(client, HermesClient)
        assert client.subject_id == "subj_001"
        assert client.session_key_hash is not None
        assert len(client.session_key_hash) == 64

    def test_create_hermes_client_fails_with_missing_params(self):
        """Factory raises ValueError for missing parameters."""
        with pytest.raises(ValueError):
            create_hermes_client("", "gumi_001", "hermes_001")

        with pytest.raises(ValueError):
            create_hermes_client("subj_001", "", "hermes_001")

        with pytest.raises(ValueError):
            create_hermes_client("subj_001", "gumi_001", "")


class TestHashForLogging:
    """Test log-safe hash function."""

    def test_hash_for_logging_produces_short_hash(self):
        """_hash_for_logging produces a short (16 char) log-safe representation."""
        key_hash = "a" * 64  # Valid sha256 hex
        result = _hash_for_logging(key_hash)
        assert len(result) == 16
        assert all(c in '0123456789abcdef' for c in result)

    def test_hash_for_logging_different_inputs(self):
        """Different inputs produce different outputs."""
        hash1 = _hash_for_logging("a" * 64)
        hash2 = _hash_for_logging("b" * 64)
        assert hash1 != hash2

    def test_hash_for_logging_is_deterministic(self):
        """Same input always produces same output."""
        key_hash = "deadbeef" + "0" * 56
        result1 = _hash_for_logging(key_hash)
        result2 = _hash_for_logging(key_hash)
        assert result1 == result2