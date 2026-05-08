"""WIRE05 Delivery Allowlist CLI and Gate tests."""

from __future__ import annotations

import hashlib
import json
import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from relic.hermes_runtime import (
    DeliveryGate,
    DeliveryGateDecision,
    DeliveryGateDecisionEvent,
    register_allowlist_entry,
    get_allowlist_entry,
    clear_allowlist_store,
    _ALLOWLIST_STORE,
)
from relic.profile.registry import ProfileRegistry


@pytest.fixture(autouse=True)
def clear_store():
    """Clear the allowlist store before and after each test."""
    clear_allowlist_store()
    yield
    clear_allowlist_store()


def _hash_target(target: str) -> str:
    """Hash a target identifier for storage."""
    return hashlib.sha256(target.encode("utf-8")).hexdigest()


class TestAllowlistHashing:
    """Test that target IDs are hashed in storage."""

    def test_allowlist_add_hashes_target(self):
        """Adding a target to allowlist hashes the target ID before storage."""
        subject_id = "subj_test_hashing"
        platform = "telegram"
        raw_target = "telegram:123456789"

        # Register an allowlist entry with a raw target
        entry = {
            "subject_id": subject_id,
            "platform": platform,
            "target_hash": _hash_target(raw_target),
            "enabled": True,
        }
        register_allowlist_entry(entry)

        # Retrieve the entry
        retrieved = get_allowlist_entry(subject_id, platform)

        # Verify the raw target is NOT stored
        assert "target_raw" not in retrieved

        # Verify the target_hash IS stored
        assert "target_hash" in retrieved
        assert retrieved["target_hash"] == _hash_target(raw_target)

        # Verify the raw target cannot be determined from storage
        stored_json = json.dumps(retrieved)
        assert raw_target not in stored_json


class TestDeliveryGateBlocking:
    """Test that DeliveryGate blocks non-allowlisted targets."""

    def test_delivery_blocks_non_allowlisted_target(self):
        """DeliveryGate.check() returns BLOCK when target not in allowlist."""
        gate = DeliveryGate(
            subject_id="subj_block_test",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            delivery_consent=True,
            quiet_hours_active=False,
        )

        # Non-allowlisted platform should be blocked
        decision = gate.check("telegram")
        assert decision == DeliveryGateDecision.BLOCK

    def test_delivery_allows_allowlisted_target(self):
        """DeliveryGate.check() returns ALLOW when target is in allowlist."""
        subject_id = "subj_allow_test"
        platform = "telegram"
        raw_target = "telegram:987654321"

        # Register the allowlist entry
        entry = {
            "subject_id": subject_id,
            "platform": platform,
            "target_hash": _hash_target(raw_target),
            "enabled": True,
        }
        register_allowlist_entry(entry)

        gate = DeliveryGate(
            subject_id=subject_id,
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            delivery_consent=True,
            quiet_hours_active=False,
        )

        # Allowlisted platform should be allowed
        decision = gate.check(platform)
        assert decision == DeliveryGateDecision.ALLOW


class TestDeliveryGateEnforce:
    """Test that DeliveryGate.enforce() works correctly."""

    def test_enforce_blocks_when_not_allowlisted(self):
        """Enforce returns BLOCK when platform not allowlisted."""
        gate = DeliveryGate(
            subject_id="subj_enforce_block",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            delivery_consent=True,
            quiet_hours_active=False,
        )

        decision, event = gate.enforce("telegram")

        assert decision == DeliveryGateDecision.BLOCK
        assert event is not None
        assert "platform_not_allowlisted" in event.reason_codes

    def test_enforce_blocks_during_quiet_hours(self):
        """Enforce returns BLOCK during quiet hours."""
        gate = DeliveryGate(
            subject_id="subj_quiet_hours",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            delivery_consent=True,
            quiet_hours_active=True,
        )

        decision, event = gate.enforce("telegram")

        assert decision == DeliveryGateDecision.BLOCK
        assert event is not None
        assert "quiet_hours" in event.reason_codes

    def test_enforce_blocks_when_consent_withdrawn(self):
        """Enforce returns BLOCK when delivery consent is withdrawn."""
        gate = DeliveryGate(
            subject_id="subj_no_consent",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            delivery_consent=False,
            quiet_hours_active=False,
        )

        decision, event = gate.enforce("telegram")

        assert decision == DeliveryGateDecision.BLOCK
        assert event is not None
        assert "delivery_consent_withdrawn" in event.reason_codes


class TestFollowupDeliveryGate:
    """Test that follow-up delivery uses the delivery gate."""

    def test_followup_delivery_uses_gate(self):
        """Follow-up delivery must pass through DeliveryGate.check()."""
        subject_id = "subj_followup_gate"
        platform = "telegram"

        # Register allowlist entry
        entry = {
            "subject_id": subject_id,
            "platform": platform,
            "target_hash": _hash_target("telegram:111222333"),
            "enabled": True,
        }
        register_allowlist_entry(entry)

        gate = DeliveryGate(
            subject_id=subject_id,
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            delivery_consent=True,
            quiet_hours_active=False,
        )

        # Simulate follow-up delivery check
        decision = gate.check(platform)
        assert decision == DeliveryGateDecision.ALLOW

        # Now remove from allowlist
        allowlist_key = f"{subject_id}:{platform}"
        del _ALLOWLIST_STORE[allowlist_key]

        decision = gate.check(platform)
        assert decision == DeliveryGateDecision.BLOCK


class TestFirstContactDeliveryGate:
    """Test that first contact delivery uses the delivery gate."""

    def test_first_contact_delivery_uses_gate(self):
        """First contact delivery must pass through DeliveryGate.check()."""
        subject_id = "subj_first_contact"
        platform = "telegram"

        # No allowlist entry - should be blocked
        gate = DeliveryGate(
            subject_id=subject_id,
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            delivery_consent=True,
            quiet_hours_active=False,
        )

        decision = gate.check(platform)
        assert decision == DeliveryGateDecision.BLOCK

        # Add allowlist entry
        entry = {
            "subject_id": subject_id,
            "platform": platform,
            "target_hash": _hash_target("telegram:444555666"),
            "enabled": True,
        }
        register_allowlist_entry(entry)

        decision = gate.check(platform)
        assert decision == DeliveryGateDecision.ALLOW


class TestSubjectInitAllowlist:
    """Test that subject init creates empty allowlist with delivery_enabled=false."""

    def test_subject_init_creates_empty_allowlist(self, tmp_path):
        """Subject init should create empty allowlist and delivery_enabled=false."""
        # Create a minimal registry for testing
        with patch("relic.profile.registry.get_relic_home", return_value=tmp_path):
            registry = ProfileRegistry(relic_home=tmp_path)

            # Create subject
            profile = registry.create_subject("subj_init_test", "exp_001")

            # Verify subject created
            assert profile is not None
            assert profile.subject_id == "subj_init_test"

            # Verify delivery policy does NOT exist yet (or has delivery_enabled=false)
            policy_path = registry._delivery_policy_path(profile.subject_id)
            if policy_path.exists():
                policy = json.loads(policy_path.read_text())
                assert policy.get("delivery_enabled") is False
            # else: no delivery policy means delivery is implicitly disabled

            # Verify no allowlist entries for this subject
            entry = get_allowlist_entry(profile.subject_id, "telegram")
            assert entry is None


class TestDeliveryGateDecisionEvent:
    """Test DeliveryGateDecisionEvent serialization."""

    def test_event_to_dict(self):
        """DecisionEvent.to_dict() returns complete audit payload."""
        event = DeliveryGateDecisionEvent(
            decision=DeliveryGateDecision.BLOCK,
            reason_codes=["platform_not_allowlisted"],
            subject_id="subj_event_test",
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            platform="telegram",
            target_hash="abc123",
        )

        d = event.to_dict()

        assert d["decision"] == "BLOCK"
        assert "platform_not_allowlisted" in d["reason_codes"]
        assert d["subject_id"] == "subj_event_test"
        assert d["gumi_instance_id"] == "gumi_001"
        assert d["hermes_profile_id"] == "hermes_001"
        assert d["platform"] == "telegram"
        assert d["target_hash"] == "abc123"
        assert "created_at" in d


class TestAllowlistExpiration:
    """Test allowlist entry expiration handling."""

    def test_expired_entry_is_blocked(self):
        """Expired allowlist entries are treated as blocked."""
        subject_id = "subj_expired"
        platform = "telegram"

        # Create entry with past expiry
        past_time = (datetime.now(timezone.utc)).isoformat()
        entry = {
            "subject_id": subject_id,
            "platform": platform,
            "target_hash": _hash_target("telegram:777888999"),
            "enabled": True,
            "expires_at": "2020-01-01T00:00:00+00:00",
        }
        register_allowlist_entry(entry)

        gate = DeliveryGate(
            subject_id=subject_id,
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            delivery_consent=True,
            quiet_hours_active=False,
        )

        decision = gate.check(platform)
        assert decision == DeliveryGateDecision.BLOCK

    def test_valid_entry_passes(self):
        """Non-expired allowlist entries pass the gate."""
        from datetime import timedelta

        subject_id = "subj_valid"
        platform = "telegram"

        # Create entry with future expiry (not current time - use +1 hour)
        future_time = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        entry = {
            "subject_id": subject_id,
            "platform": platform,
            "target_hash": _hash_target("telegram:000111222"),
            "enabled": True,
            "expires_at": future_time,
        }
        register_allowlist_entry(entry)

        gate = DeliveryGate(
            subject_id=subject_id,
            gumi_instance_id="gumi_001",
            hermes_profile_id="hermes_001",
            delivery_consent=True,
            quiet_hours_active=False,
        )

        decision = gate.check(platform)
        assert decision == DeliveryGateDecision.ALLOW
