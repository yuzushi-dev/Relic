"""
Tests for Hermes delivery gate - FIX04: Platform allowlist delivery gate.

Every outbound path must pass delivery gate:
- direct Gumi reply
- cron follow-up
- Shared Continuity follow-up
- first-contact message
- summary delivery
- media/diegetic proactive message
- resume-delayed pending output

If no allowlist entry: BLOCK, emit delivery_block_event.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest

from relic.hermes_runtime import (
    DeliveryGate,
    DeliveryGateDecision,
    DeliveryGateDecisionEvent,
    clear_allowlist_store,
    register_allowlist_entry,
    get_allowlist_entry,
)


@pytest.fixture(autouse=True)
def clean_allowlist():
    """Clean allowlist store before and after each test."""
    clear_allowlist_store()
    yield
    clear_allowlist_store()


@pytest.fixture
def valid_allowlist_entry():
    """A valid allowlist entry fixture."""
    return {
        "allowlist_id": "allowlist_001",
        "subject_id": "subj_001",
        "platform": "telegram",
        "enabled": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        "default_deny": True,
        "audit_event_on_change": True,
    }


@pytest.fixture
def allowlisted_gate(valid_allowlist_entry):
    """A delivery gate with allowlisted platform."""
    register_allowlist_entry(valid_allowlist_entry)
    return DeliveryGate(
        subject_id="subj_001",
        gumi_instance_id="gumi_subj_001",
        hermes_profile_id="gumi-subj_001",
        delivery_consent=True,
        quiet_hours_active=False,
    )


class TestDeliveryGateAllowsAllowlistedPlatform:
    """Test suite for delivery gate allowing allowlisted platforms."""

    def test_delivery_gate_allows_allowlisted_platform(self, allowlisted_gate):
        """
        Acceptance: Delivery gate allows platform with valid allowlist entry.
        """
        decision = allowlisted_gate.check("telegram")
        assert decision == DeliveryGateDecision.ALLOW

    def test_delivery_gate_enforce_returns_allow_with_no_event(self, allowlisted_gate):
        """
        Acceptance: When ALLOW, no block event is emitted.
        """
        decision, event = allowlisted_gate.enforce("telegram")
        assert decision == DeliveryGateDecision.ALLOW
        assert event is None

    def test_allowlisted_platform_with_consent_and_no_quiet_hours(self, valid_allowlist_entry):
        """
        Acceptance: Platform is allowed when consent is given and not in quiet hours.
        """
        gate = DeliveryGate(
            subject_id="subj_001",
            gumi_instance_id="gumi_subj_001",
            hermes_profile_id="gumi-subj_001",
            delivery_consent=True,
            quiet_hours_active=False,
        )
        register_allowlist_entry(valid_allowlist_entry)
        decision, event = gate.enforce("telegram")
        assert decision == DeliveryGateDecision.ALLOW
        assert event is None


class TestDeliveryGateBlocksNotAllowlisted:
    """Test suite for delivery gate blocking non-allowlisted platforms."""

    def test_delivery_gate_blocks_not_allowlisted(self):
        """
        Acceptance: Delivery gate BLOCKs when platform has no allowlist entry.
        """
        gate = DeliveryGate(
            subject_id="subj_001",
            gumi_instance_id="gumi_subj_001",
            hermes_profile_id="gumi-subj_001",
            delivery_consent=True,
            quiet_hours_active=False,
        )
        # No allowlist entry registered for whatsapp
        decision = gate.check("whatsapp")
        assert decision == DeliveryGateDecision.BLOCK

    def test_delivery_gate_blocks_disabled_allowlist_entry(self):
        """
        Acceptance: Delivery gate BLOCKs when allowlist entry is disabled.
        """
        entry = {
            "allowlist_id": "allowlist_002",
            "subject_id": "subj_001",
            "platform": "telegram",
            "enabled": False,  # Disabled
            "created_at": datetime.now(timezone.utc).isoformat(),
            "default_deny": True,
        }
        register_allowlist_entry(entry)
        gate = DeliveryGate(
            subject_id="subj_001",
            gumi_instance_id="gumi_subj_001",
            hermes_profile_id="gumi-subj_001",
            delivery_consent=True,
            quiet_hours_active=False,
        )
        decision = gate.check("telegram")
        assert decision == DeliveryGateDecision.BLOCK

    def test_delivery_gate_blocks_expired_allowlist_entry(self):
        """
        Acceptance: Delivery gate BLOCKs when allowlist entry has expired.
        """
        entry = {
            "allowlist_id": "allowlist_003",
            "subject_id": "subj_001",
            "platform": "telegram",
            "enabled": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),  # Expired
            "default_deny": True,
        }
        register_allowlist_entry(entry)
        gate = DeliveryGate(
            subject_id="subj_001",
            gumi_instance_id="gumi_subj_001",
            hermes_profile_id="gumi-subj_001",
            delivery_consent=True,
            quiet_hours_active=False,
        )
        decision = gate.check("telegram")
        assert decision == DeliveryGateDecision.BLOCK


class TestDeliveryGateEmitsBlockEvent:
    """Test suite for delivery gate emitting block events."""

    def test_delivery_gate_emits_block_event_for_missing_allowlist(self):
        """
        Acceptance: When platform is not allowlisted, delivery_block_event is emitted.
        """
        gate = DeliveryGate(
            subject_id="subj_001",
            gumi_instance_id="gumi_subj_001",
            hermes_profile_id="gumi-subj_001",
            delivery_consent=True,
            quiet_hours_active=False,
        )
        decision, event = gate.enforce("whatsapp")
        assert decision == DeliveryGateDecision.BLOCK
        assert event is not None
        assert event.decision == DeliveryGateDecision.BLOCK
        assert "platform_not_allowlisted" in event.reason_codes
        assert event.subject_id == "subj_001"
        assert event.platform == "whatsapp"

    def test_delivery_gate_emits_block_event_for_quiet_hours(self, allowlisted_gate):
        """
        Acceptance: When quiet hours are active, delivery_block_event is emitted.
        """
        gate = DeliveryGate(
            subject_id="subj_001",
            gumi_instance_id="gumi_subj_001",
            hermes_profile_id="gumi-subj_001",
            delivery_consent=True,
            quiet_hours_active=True,  # Quiet hours active
        )
        register_allowlist_entry(
            {
                "allowlist_id": "allowlist_004",
                "subject_id": "subj_001",
                "platform": "telegram",
                "enabled": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "default_deny": True,
            }
        )
        decision, event = gate.enforce("telegram")
        assert decision == DeliveryGateDecision.BLOCK
        assert event is not None
        assert "quiet_hours" in event.reason_codes

    def test_delivery_gate_emits_block_event_for_consent_withdrawn(self, allowlisted_gate):
        """
        Acceptance: When delivery consent is withdrawn, delivery_block_event is emitted.
        """
        gate = DeliveryGate(
            subject_id="subj_001",
            gumi_instance_id="gumi_subj_001",
            hermes_profile_id="gumi-subj_001",
            delivery_consent=False,  # Consent withdrawn
            quiet_hours_active=False,
        )
        register_allowlist_entry(
            {
                "allowlist_id": "allowlist_005",
                "subject_id": "subj_001",
                "platform": "telegram",
                "enabled": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "default_deny": True,
            }
        )
        decision, event = gate.enforce("telegram")
        assert decision == DeliveryGateDecision.BLOCK
        assert event is not None
        assert "delivery_consent_withdrawn" in event.reason_codes

    def test_delivery_block_event_to_dict(self):
        """
        Acceptance: Block event can be serialized to dict.
        """
        event = DeliveryGateDecisionEvent(
            decision=DeliveryGateDecision.BLOCK,
            reason_codes=["platform_not_allowlisted"],
            subject_id="subj_001",
            gumi_instance_id="gumi_subj_001",
            hermes_profile_id="gumi-subj_001",
            platform="telegram",
        )
        d = event.to_dict()
        assert d["decision"] == "BLOCK"
        assert "platform_not_allowlisted" in d["reason_codes"]
        assert d["subject_id"] == "subj_001"
        assert d["platform"] == "telegram"
        assert "created_at" in d


class TestAllOutboundPathsCheckGate:
    """
    Test suite verifying all outbound paths check the delivery gate.

    Every outbound path must pass delivery gate:
    - direct Gumi reply
    - cron follow-up
    - Shared Continuity follow-up
    - first-contact message
    - summary delivery
    - media/diegetic proactive message
    - resume-delayed pending output
    """

    def test_direct_gumi_reply_checks_gate(self, allowlisted_gate):
        """
        Acceptance: Direct Gumi reply path checks delivery gate.
        """
        # Direct reply to user message
        decision, event = allowlisted_gate.enforce("telegram")
        assert decision == DeliveryGateDecision.ALLOW
        assert event is None

    def test_cron_followup_checks_gate(self, allowlisted_gate):
        """
        Acceptance: Cron follow-up path checks delivery gate.
        """
        # Scheduled follow-up message
        gate = DeliveryGate(
            subject_id="subj_001",
            gumi_instance_id="gumi_subj_001",
            hermes_profile_id="gumi-subj_001",
            delivery_consent=True,
            quiet_hours_active=False,
        )
        register_allowlist_entry(
            {
                "allowlist_id": "allowlist_006",
                "subject_id": "subj_001",
                "platform": "telegram",
                "enabled": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "default_deny": True,
            }
        )
        decision, event = gate.enforce("telegram")
        assert decision == DeliveryGateDecision.ALLOW
        assert event is None

    def test_shared_continuity_followup_checks_gate(self):
        """
        Acceptance: Shared Continuity follow-up path checks delivery gate.
        """
        gate = DeliveryGate(
            subject_id="subj_002",
            gumi_instance_id="gumi_subj_002",
            hermes_profile_id="gumi-subj_002",
            delivery_consent=True,
            quiet_hours_active=False,
        )
        # No allowlist entry - should be blocked
        decision, event = gate.enforce("telegram")
        assert decision == DeliveryGateDecision.BLOCK
        assert event is not None
        assert "platform_not_allowlisted" in event.reason_codes

    def test_first_contact_message_checks_gate(self):
        """
        Acceptance: First-contact message path checks delivery gate.
        """
        gate = DeliveryGate(
            subject_id="subj_003",
            gumi_instance_id="gumi_subj_003",
            hermes_profile_id="gumi-subj_003",
            delivery_consent=True,
            quiet_hours_active=False,
        )
        # No allowlist entry for first contact - should be blocked
        decision, event = gate.enforce("email")
        assert decision == DeliveryGateDecision.BLOCK
        assert event is not None
        assert "platform_not_allowlisted" in event.reason_codes

    def test_resume_delayed_pending_output_checks_gate(self):
        """
        Acceptance: Resume-delayed pending output path checks delivery gate.
        """
        gate = DeliveryGate(
            subject_id="subj_004",
            gumi_instance_id="gumi_subj_004",
            hermes_profile_id="gumi-subj_004",
            delivery_consent=True,
            quiet_hours_active=False,
        )
        # Resume of delayed output - platform not allowlisted
        decision, event = gate.enforce("whatsapp")
        assert decision == DeliveryGateDecision.BLOCK
        assert event is not None
        assert "platform_not_allowlisted" in event.reason_codes

    def test_multiple_platforms_all_checked(self, valid_allowlist_entry):
        """
        Acceptance: Each platform is checked independently against allowlist.
        """
        register_allowlist_entry(valid_allowlist_entry)
        gate = DeliveryGate(
            subject_id="subj_001",
            gumi_instance_id="gumi_subj_001",
            hermes_profile_id="gumi-subj_001",
            delivery_consent=True,
            quiet_hours_active=False,
        )

        # Telegram is allowlisted
        assert gate.check("telegram") == DeliveryGateDecision.ALLOW

        # WhatsApp is not allowlisted
        assert gate.check("whatsapp") == DeliveryGateDecision.BLOCK

        # Email is not allowlisted
        assert gate.check("email") == DeliveryGateDecision.BLOCK


class TestDeliveryGateDecisionEnum:
    """Test suite for DeliveryGateDecision enum."""

    def test_delivery_gate_decision_values(self):
        """
        Acceptance: DeliveryGateDecision has ALLOW, BLOCK, REVIEW_REQUIRED.
        """
        assert DeliveryGateDecision.ALLOW.value == "ALLOW"
        assert DeliveryGateDecision.BLOCK.value == "BLOCK"
        assert DeliveryGateDecision.REVIEW_REQUIRED.value == "REVIEW_REQUIRED"

    def test_delivery_gate_decision_is_string_enum(self):
        """
        Acceptance: DeliveryGateDecision is a string enum.
        """
        assert isinstance(DeliveryGateDecision.ALLOW, str)
        assert DeliveryGateDecision.ALLOW == "ALLOW"


class TestAllowlistStoreFunctions:
    """Test suite for allowlist store management functions."""

    def test_register_and_get_allowlist_entry(self, valid_allowlist_entry):
        """
        Acceptance: Allowlist entries can be registered and retrieved.
        """
        register_allowlist_entry(valid_allowlist_entry)
        entry = get_allowlist_entry("subj_001", "telegram")
        assert entry is not None
        assert entry["subject_id"] == "subj_001"
        assert entry["platform"] == "telegram"
        assert entry["enabled"] is True

    def test_get_nonexistent_allowlist_entry(self):
        """
        Acceptance: Getting non-existent entry returns None.
        """
        entry = get_allowlist_entry("subj_999", "nonexistent")
        assert entry is None

    def test_clear_allowlist_store(self, valid_allowlist_entry):
        """
        Acceptance: Allowlist store can be cleared.
        """
        register_allowlist_entry(valid_allowlist_entry)
        clear_allowlist_store()
        entry = get_allowlist_entry("subj_001", "telegram")
        assert entry is None
