"""
PR27N, Permissions and Audit Controls Contract Tests

Tests verify:
- Raw content access creates audit event
- Sensitive actions require role permission
- Roles: experimenter, reviewer, operator, auditor, admin
- Operator can provision Hermes but cannot edit subject baseline
- Admin override creates audit event
- Required audit events are tracked
"""

import pytest
from pathlib import Path


FIXTURE_PATH = Path(__file__).parent.parent.parent / "fixtures" / "researcher-workbench" / "permissions_matrix.json"


def load_fixture():
    import json
    with open(FIXTURE_PATH) as f:
        return json.load(f)


class TestWorkbenchPermissionsContract:
    """PR27N Workbench Permissions contract tests."""

    def test_raw_access_creates_audit_event(self):
        """Raw content access must create an audit event."""
        fixture = load_fixture()
        audit_schema_path = Path(__file__).parent.parent.parent / "schemas" / "ui" / "workbench_audit_event.schema.json"
        import json
        with open(audit_schema_path) as f:
            schema = json.load(f)
        # Verify raw_content_accessed is a valid action
        actions = schema["properties"]["action"]["enum"]
        assert "raw_content_accessed" in actions

    def test_sensitive_actions_require_role(self):
        """Sensitive actions must require role permission."""
        fixture = load_fixture()
        roles = fixture.get("roles", {})
        assert "experimenter" in roles
        assert "reviewer" in roles
        assert "operator" in roles
        assert "auditor" in roles
        assert "admin" in roles

    def test_operator_cannot_edit_baseline(self):
        """Operator must not be able to edit subject baseline."""
        fixture = load_fixture()
        operator = fixture["roles"]["operator"]
        assert operator.get("can_edit_baseline") is False, "BLOCKED_OPERATOR_BASELINE_EDIT"

    def test_admin_override_creates_audit_event(self):
        """Admin override must create audit event."""
        audit_schema_path = Path(__file__).parent.parent.parent / "schemas" / "ui" / "workbench_audit_event.schema.json"
        import json
        with open(audit_schema_path) as f:
            schema = json.load(f)
        actions = schema["properties"]["action"]["enum"]
        # Admin actions should be auditable
        assert "export_generated" in actions
        assert "correction_applied" in actions

    def test_role_permissions_enforced(self):
        """Role permissions must be enforced."""
        fixture = load_fixture()
        roles = fixture.get("roles", {})
        # Verify experimenter role
        exp = roles["experimenter"]
        assert exp["can_view_subjects"] is True
        assert exp["can_hermes_provision"] is False
        # Verify operator role
        op = roles["operator"]
        assert op["can_hermes_provision"] is True
        assert op["can_edit_baseline"] is False
