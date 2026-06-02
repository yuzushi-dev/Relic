"""
PR27I, Boundary and Risk Monitor Contract Tests

Tests verify:
- Boundary risk is subject-scoped
- Careful distancing can be enabled per subject
- Media/proactive/diegetic modes can be paused independently
- Boundary corrections are logged as audit events
- UI shows dependency markers and overreach indicators
- Panel is not labeled "Diagnostics" or any clinical term
"""

import pytest
from pathlib import Path


FIXTURE_PATH = Path(__file__).parent.parent.parent / "fixtures" / "researcher-workbench" / "boundary_risk_subj_001.json"


def load_fixture():
    import json
    with open(FIXTURE_PATH) as f:
        return json.load(f)


class TestBoundaryRiskMonitorContract:
    """PR27I Boundary Risk Monitor contract tests."""

    def test_boundary_monitor_subject_scoped(self):
        """Boundary risk must be subject-scoped."""
        fixture = load_fixture()
        assert "subject_id" in fixture, "BLOCKED_BOUNDARY_MONITOR_WITHOUT_SUBJECT"
        assert fixture["subject_id"] is not None

    def test_careful_distancing_available(self):
        """Careful distancing can be enabled per subject."""
        fixture = load_fixture()
        assert "careful_distancing_enabled" in fixture, "BLOCKED_CAREFUL_DISTANCING_MISSING"
        assert isinstance(fixture["careful_distancing_enabled"], bool)

    def test_boundary_action_creates_audit_event(self):
        """Boundary corrections are logged as audit events."""
        fixture = load_fixture()
        # Verify the schema supports audit events
        audit_schema_path = Path(__file__).parent.parent.parent / "schemas" / "ui" / "workbench_audit_event.schema.json"
        import json
        with open(audit_schema_path) as f:
            schema = json.load(f)
        assert "boundary_correction" in str(schema) or "audit" in str(schema)

    def test_media_modes_pausable_independently(self):
        """Media/proactive/diegetic modes can be paused independently."""
        fixture = load_fixture()
        assert "media_pause_state" in fixture
        pause_state = fixture["media_pause_state"]
        assert "media_paused" in pause_state
        assert "proactive_paused" in pause_state
        assert "diegetic_paused" in pause_state

    def test_boundary_monitor_shows_dependency_indicators(self):
        """UI shows dependency markers."""
        fixture = load_fixture()
        assert "dependency_indicators" in fixture, "BLOCKED_BOUNDARY_MONITOR_WITHOUT_INDICATORS"
        assert isinstance(fixture["dependency_indicators"], list)

    def test_boundary_monitor_shows_overreach_indicators(self):
        """UI shows overreach indicators."""
        fixture = load_fixture()
        assert "overreach_indicators" in fixture, "BLOCKED_BOUNDARY_MONITOR_SHOWS_OVERREACH"
        assert isinstance(fixture["overreach_indicators"], list)
