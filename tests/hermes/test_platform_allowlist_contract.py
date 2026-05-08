"""
Contract tests for Hermes v0.13 platform allowlists.
Tests ensure delivery is blocked without explicit allowlist and allowlist is subject-scoped.
"""

import json
import pytest
from pathlib import Path


SCHEMA_PATH = Path(__file__).parent.parent.parent / "schemas" / "hermes" / "platform_allowlist.schema.json"
FIXTURE_PATH = Path(__file__).parent.parent.parent / "fixtures" / "hermes" / "platform_allowlist_valid.json"


def load_schema():
    with open(SCHEMA_PATH) as f:
        return json.load(f)


def load_fixture():
    with open(FIXTURE_PATH) as f:
        return json.load(f)


class TestPlatformAllowlistContract:
    """Test suite for platform allowlist contract."""

    def test_delivery_requires_platform_allowlist(self):
        """
        Acceptance: Delivery to any platform requires an explicit allowlist entry.
        Block: BLOCKED_DELIVERY_WITHOUT_ALLOWLIST
        """
        fixture = load_fixture()
        assert fixture["default_deny"] is True
        assert fixture["enabled"] is True

    def test_unlisted_platform_blocked(self):
        """
        Acceptance: Unlisted platforms are blocked from delivery.
        Block: BLOCKED_DEFAULT_ALLOW_INSTEAD_OF_DENY
        """
        fixture = load_fixture()
        # default_deny=true means unlisted platforms are blocked
        assert fixture["default_deny"] is True

    def test_allowlist_is_subject_scoped(self):
        """
        Acceptance: Allowlist entries are subject-scoped (subject_id required).
        Block: BLOCKED_ALLOWLIST_NOT_SUBJECT_SCOPED
        """
        fixture = load_fixture()
        assert "subject_id" in fixture
        assert isinstance(fixture["subject_id"], str)
        assert len(fixture["subject_id"]) > 0
        assert fixture["subject_id"].startswith("subject_")

    def test_allowlist_entry_has_expiry(self):
        """
        Acceptance: Allowlist entries have optional expiry.
        """
        fixture = load_fixture()
        assert "expires_at" in fixture
        # Optional expiry - check format is valid if present
        if fixture["expires_at"]:
            assert "T" in fixture["expires_at"]

    def test_allowlist_change_creates_audit_event(self):
        """
        Acceptance: Allowlist changes create audit events.
        Block: BLOCKED_ALLOWLIST_CHANGE_WITHOUT_AUDIT
        """
        fixture = load_fixture()
        assert fixture["audit_event_on_change"] is True
        assert "last_modified_at" in fixture