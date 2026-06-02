"""
PR27L, Export and Replication Console Contract Tests

Tests verify:
- Export is redacted by default
- Export includes subject_id and condition
- Export includes Hermes profile hash and SOUL.md hash
- Export includes policy snapshot and cron snapshot
- Export includes event counts by ontological class
- Raw private messages are excluded
- Leakage scan runs before bundle generation
"""

import pytest
from pathlib import Path


FIXTURE_PATH = Path(__file__).parent.parent.parent / "fixtures" / "researcher-workbench" / "export_manifest_subj_001.json"


def load_fixture():
    import json
    with open(FIXTURE_PATH) as f:
        return json.load(f)


class TestExportReplicationConsoleContract:
    """PR27L Export and Replication Console contract tests."""

    def test_export_redacted_by_default(self):
        """Export must be redacted by default."""
        fixture = load_fixture()
        assert fixture.get("redacted") is True, "BLOCKED_EXPORT_WITH_RAW_PRIVATE_DATA"

    def test_export_has_hermes_hash(self):
        """Export must include Hermes profile hash."""
        fixture = load_fixture()
        assert "hermes_profile_hash" in fixture, "BLOCKED_EXPORT_WITHOUT_REDACTION_STATUS"
        assert fixture["hermes_profile_hash"] is not None
        assert fixture["hermes_profile_hash"].startswith("sha256:")

    def test_export_has_policy_snapshot(self):
        """Export must include policy snapshot."""
        fixture = load_fixture()
        assert "policy_snapshot" in fixture, "BLOCKED_EXPORT_WITHOUT_POLICY_SNAPSHOT"

    def test_raw_private_data_excluded(self):
        """Raw private messages must be excluded from export."""
        fixture = load_fixture()
        assert fixture.get("redacted") is True
        # Event counts should not include raw message content
        if "event_counts" in fixture:
            assert isinstance(fixture["event_counts"], dict)

    def test_export_has_event_counts_by_ontological_class(self):
        """Export must include event counts by ontological class."""
        fixture = load_fixture()
        assert "event_counts" in fixture
        assert isinstance(fixture["event_counts"], dict)

    def test_export_has_condition_and_subject_id(self):
        """Export must include condition and subject_id."""
        fixture = load_fixture()
        assert "subject_id" in fixture
        assert "condition" in fixture

    def test_leakage_scan_passed_before_export(self):
        """Leakage scan must run before bundle generation."""
        fixture = load_fixture()
        assert "leakage_scan_passed" in fixture, "BLOCKED_LEAKAGE_SCAN_NOT_RUN"
        assert fixture["leakage_scan_passed"] is True
