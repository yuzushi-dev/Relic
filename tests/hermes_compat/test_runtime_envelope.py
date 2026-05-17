"""
Tests for HermesRuntimeEnvelope and IdentityMapper.

These tests verify the Phase 1 implementation:
- Envelope creation and validation
- Identity mapping strategies
- Redaction status tracking
- Session key binding
"""

import pytest
from datetime import datetime, timezone
from relic.hermes_adapter.envelope import HermesRuntimeEnvelope, MetadataRedactionStatus
from relic.hermes_adapter.identity import (
    IdentityMapper,
    SubjectMapping,
    MappingStrategy,
    ConsentRequiredError,
)


class TestHermesRuntimeEnvelope:
    """Tests for HermesRuntimeEnvelope dataclass."""

    def test_create_minimal_envelope(self):
        """Test creating envelope with minimal fields."""
        envelope = HermesRuntimeEnvelope()
        assert envelope.schema_version == "relic.hermes_runtime_envelope.v1"
        assert envelope.metadata_redaction_status == MetadataRedactionStatus.HASH_ONLY
        assert envelope.trace_id is None
        assert envelope.subject_ref is None

    def test_create_full_envelope(self):
        """Test creating envelope with all fields."""
        envelope = HermesRuntimeEnvelope(
            trace_id="test-trace-123",
            session_id="session-abc",
            chat_id="chat-xyz",
            platform="telegram",
            channel_ref="channel-123",
            sender_ref="sender-456",
            subject_ref="subject-789",
            hermes_profile_id="profile-default",
            gumi_instance_id="gumi-main",
            model="gpt-4",
            turn_index=5,
            tool_call_id="tool-call-001",
            message_ref="msg-ref-abc",
            message_hash="sha256:deadbeef",
            metadata_redaction_status=MetadataRedactionStatus.REDACTED,
        )
        assert envelope.trace_id == "test-trace-123"
        assert envelope.turn_index == 5
        assert envelope.metadata_redaction_status == MetadataRedactionStatus.REDACTED

    def test_trace_id_minimum_length(self):
        """Test that trace_id must be at least 8 characters."""
        with pytest.raises(ValueError, match="trace_id must be at least 8 characters"):
            HermesRuntimeEnvelope(trace_id="short")

    def test_turn_index_non_negative(self):
        """Test that turn_index must be non-negative."""
        with pytest.raises(ValueError, match="turn_index must be non-negative"):
            HermesRuntimeEnvelope(turn_index=-1)

    def test_message_hash_auto_prefix(self):
        """Test that message_hash gets sha256: prefix if missing."""
        envelope = HermesRuntimeEnvelope(message_hash="deadbeef")
        assert envelope.message_hash == "sha256:deadbeef"

    def test_message_hash_preserve_prefix(self):
        """Test that existing sha256: prefix is preserved."""
        envelope = HermesRuntimeEnvelope(message_hash="sha256:abc123")
        assert envelope.message_hash == "sha256:abc123"

    def test_to_dict(self):
        """Test envelope serialization to dictionary."""
        envelope = HermesRuntimeEnvelope(
            trace_id="test-trace-456",
            platform="whatsapp",
            subject_ref="subject-123",
        )
        data = envelope.to_dict()
        assert data["schema_version"] == "relic.hermes_runtime_envelope.v1"
        assert data["trace_id"] == "test-trace-456"
        assert data["platform"] == "whatsapp"
        assert data["subject_ref"] == "subject-123"
        assert data["metadata_redaction_status"] == "hash_only"
        assert "received_at" in data

    def test_from_dict(self):
        """Test envelope deserialization from dictionary."""
        data = {
            "schema_version": "relic.hermes_runtime_envelope.v1",
            "trace_id": "test-trace-789",
            "platform": "telegram",
            "subject_ref": "subject-456",
            "metadata_redaction_status": "redacted",
            "turn_index": 3,
        }
        envelope = HermesRuntimeEnvelope.from_dict(data)
        assert envelope.trace_id == "test-trace-789"
        assert envelope.platform == "telegram"
        assert envelope.metadata_redaction_status == MetadataRedactionStatus.REDACTED
        assert envelope.turn_index == 3

    def test_from_dict_with_iso_timestamp(self):
        """Test envelope deserialization with ISO timestamp."""
        data = {
            "trace_id": "test-trace-000",
            "received_at": "2026-05-16T12:00:00+00:00",
        }
        envelope = HermesRuntimeEnvelope.from_dict(data)
        assert isinstance(envelope.received_at, datetime)

    def test_with_subject_ref(self):
        """Test creating new envelope with updated subject_ref."""
        original = HermesRuntimeEnvelope(trace_id="test-trace-111")
        updated = original.with_subject_ref("new-subject-ref")
        assert original.subject_ref is None
        assert updated.subject_ref == "new-subject-ref"
        assert updated.trace_id == "test-trace-111"  # Immutable

    def test_bind_session_key(self):
        """Test binding session key to envelope."""
        original = HermesRuntimeEnvelope(trace_id="test-trace-222")
        bound = original.bind_session_key("abc123hash")
        assert original.session_key_hash is None
        assert bound.session_key_hash == "abc123hash"

    def test_envelope_is_frozen(self):
        """Test that envelope is immutable."""
        envelope = HermesRuntimeEnvelope(trace_id="test-trace-333")
        with pytest.raises(Exception):  # frozen dataclass raises
            envelope.trace_id = "modified"


class TestIdentityMapper:
    """Tests for IdentityMapper."""

    def test_hashed_mapping_default(self):
        """Test default hashed mapping strategy."""
        mapper = IdentityMapper()
        mapping = mapper.map_sender_to_subject(
            sender_id="user123",
            platform="telegram",
            gumi_instance_id="gumi-main",
            hermes_profile_id="profile-default",
        )
        assert mapping.mapping_strategy == MappingStrategy.HASHED
        assert mapping.subject_ref is not None
        assert mapping.sender_ref is not None
        assert mapping.subject_ref != "user123"  # Should be hashed

    def test_hashed_mapping_is_deterministic(self):
        """Test that hashed mapping produces consistent results."""
        mapper = IdentityMapper()
        mapping1 = mapper.map_sender_to_subject(
            sender_id="user123",
            platform="telegram",
            gumi_instance_id="gumi-main",
            hermes_profile_id="profile-default",
        )
        mapping2 = mapper.map_sender_to_subject(
            sender_id="user123",
            platform="telegram",
            gumi_instance_id="gumi-main",
            hermes_profile_id="profile-default",
        )
        assert mapping1.subject_ref == mapping2.subject_ref

    def test_hashed_mapping_differs_by_platform(self):
        """Test that same sender_id produces different subject_ref per platform."""
        mapper = IdentityMapper()
        mapping_telegram = mapper.map_sender_to_subject(
            sender_id="user123",
            platform="telegram",
            gumi_instance_id="gumi-main",
            hermes_profile_id="profile-default",
        )
        mapping_whatsapp = mapper.map_sender_to_subject(
            sender_id="user123",
            platform="whatsapp",
            gumi_instance_id="gumi-main",
            hermes_profile_id="profile-default",
        )
        assert mapping_telegram.subject_ref != mapping_whatsapp.subject_ref

    def test_explicit_mapping(self):
        """Test explicit configured mapping."""
        mapper = IdentityMapper(mapping_strategy=MappingStrategy.CONFIGURED)
        mapper.register_explicit_mapping(
            sender_id="vip-user",
            platform="telegram",
            hermes_profile_id="profile-default",
            subject_ref="subject-vip-001",
        )
        mapping = mapper.map_sender_to_subject(
            sender_id="vip-user",
            platform="telegram",
            gumi_instance_id="gumi-main",
            hermes_profile_id="profile-default",
        )
        assert mapping.subject_ref == "subject-vip-001"
        assert mapping.mapping_strategy == MappingStrategy.CONFIGURED

    def test_consent_based_mapping_requires_consent(self):
        """Test that consent-based mapping requires consent."""
        mapper = IdentityMapper(mapping_strategy=MappingStrategy.CONSENT_BASED)
        with pytest.raises(ConsentRequiredError):
            mapper.map_sender_to_subject(
                sender_id="user123",
                platform="telegram",
                gumi_instance_id="gumi-main",
                hermes_profile_id="profile-default",
                chat_id="chat-001",
            )

    def test_consent_based_mapping_with_consent(self):
        """Test consent-based mapping after granting consent."""
        mapper = IdentityMapper(mapping_strategy=MappingStrategy.CONSENT_BASED)
        mapper.grant_consent("user123", "telegram")
        mapping = mapper.map_sender_to_subject(
            sender_id="user123",
            platform="telegram",
            gumi_instance_id="gumi-main",
            hermes_profile_id="profile-default",
            chat_id="chat-001",
        )
        assert mapping.consent_granted is True
        assert mapping.subject_ref is not None

    def test_consent_revoke(self):
        """Test revoking consent."""
        mapper = IdentityMapper(mapping_strategy=MappingStrategy.CONSENT_BASED)
        mapper.grant_consent("user123", "telegram")
        mapper.revoke_consent("user123", "telegram")
        with pytest.raises(ConsentRequiredError):
            mapper.map_sender_to_subject(
                sender_id="user123",
                platform="telegram",
                gumi_instance_id="gumi-main",
                hermes_profile_id="profile-default",
                chat_id="chat-001",
            )

    def test_missing_sender_id_raises(self):
        """Test that missing sender_id raises ValueError."""
        mapper = IdentityMapper()
        with pytest.raises(ValueError, match="sender_id is required"):
            mapper.map_sender_to_subject(
                sender_id="",
                platform="telegram",
                gumi_instance_id="gumi-main",
                hermes_profile_id="profile-default",
            )

    def test_missing_platform_raises(self):
        """Test that missing platform raises ValueError."""
        mapper = IdentityMapper()
        with pytest.raises(ValueError, match="platform is required"):
            mapper.map_sender_to_subject(
                sender_id="user123",
                platform="",
                gumi_instance_id="gumi-main",
                hermes_profile_id="profile-default",
            )

    def test_mapping_to_dict(self):
        """Test SubjectMapping serialization."""
        mapper = IdentityMapper()
        mapping = mapper.map_sender_to_subject(
            sender_id="user123",
            platform="telegram",
            gumi_instance_id="gumi-main",
            hermes_profile_id="profile-default",
        )
        data = mapping.to_dict()
        assert "subject_ref" in data
        assert "sender_ref" in data
        assert "platform_scope" in data
        assert "mapping_strategy" in data
        assert data["mapping_strategy"] == "hashed"
        assert "mapped_at" in data


class TestEnvelopeIdentityIntegration:
    """Integration tests for envelope + identity mapping."""

    def test_create_envelope_from_mapping(self):
        """Test creating envelope using identity mapper result."""
        mapper = IdentityMapper()
        mapping = mapper.map_sender_to_subject(
            sender_id="user123",
            platform="telegram",
            gumi_instance_id="gumi-main",
            hermes_profile_id="profile-default",
        )
        envelope = HermesRuntimeEnvelope(
            trace_id="integration-test-001",
            sender_ref=mapping.sender_ref,
            subject_ref=mapping.subject_ref,
            platform=mapping.platform_scope,
        )
        assert envelope.sender_ref == mapping.sender_ref
        assert envelope.subject_ref == mapping.subject_ref
        assert envelope.platform == "telegram"

    def test_envelope_with_bound_session_key(self):
        """Test envelope with session key binding after identity mapping."""
        from relic.hermes_runtime import HermesSessionKey

        mapper = IdentityMapper()
        mapping = mapper.map_sender_to_subject(
            sender_id="user123",
            platform="telegram",
            gumi_instance_id="gumi-main",
            hermes_profile_id="profile-default",
        )
        envelope = HermesRuntimeEnvelope(
            trace_id="session-key-test-001",
            subject_ref=mapping.subject_ref,
        )
        session_key_hash = HermesSessionKey.derive(
            subject_id=mapping.subject_ref,
            gumi_instance_id="gumi-main",
            hermes_profile_id="profile-default",
        )
        bound_envelope = envelope.bind_session_key(session_key_hash)
        assert bound_envelope.session_key_hash == session_key_hash
        assert bound_envelope.subject_ref == mapping.subject_ref
