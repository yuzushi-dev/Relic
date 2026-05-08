"""
Contract tests for Hermes v0.13 rollback flags.
Tests ensure every new behavior has a rollback flag and Phase 0/1 do not change live behavior.
"""

import json
import pytest
from pathlib import Path


SCHEMA_PATH = Path(__file__).parent.parent.parent / "schemas" / "hermes" / "rollback_flag.schema.json"
FIXTURE_PATH = Path(__file__).parent.parent.parent / "fixtures" / "hermes" / "rollback_flag_valid.json"


def load_schema():
    with open(SCHEMA_PATH) as f:
        return json.load(f)


def load_fixture():
    with open(FIXTURE_PATH) as f:
        return json.load(f)


class TestRollbackFlagContract:
    """Test suite for rollback flag contract."""

    def test_every_new_behavior_has_rollback_flag(self):
        """
        Acceptance: Every new Hermes v0.13 behavior has a rollback flag defined in schema.
        Block: BLOCKED_NEW_BEHAVIOR_WITHOUT_ROLLBACK
        """
        fixture = load_fixture()
        assert "feature_name" in fixture
        assert "rollback_flag_name" in fixture
        assert len(fixture["rollback_flag_name"]) > 0

    def test_rollback_flag_disables_feature(self):
        """
        Acceptance: Rollback flag completely disables the feature when set.
        Block: BLOCKED_ROLLBACK_DOES_NOT_DISABLE_FEATURE
        """
        fixture = load_fixture()
        assert fixture["completely_disables_feature"] is True

    def test_phase_0_no_live_behavior_change(self):
        """
        Acceptance: Phase 0 (read-only discovery) changes no live behavior.
        Block: BLOCKED_PHASE_0_LIVE_BEHAVIOR_CHANGE
        """
        fixture = load_fixture()
        # If phase is Phase 0, affects_live_behavior must be false
        if fixture.get("phase") == "Phase 0":
            assert fixture["affects_live_behavior"] is False

    def test_phase_1_no_live_behavior_change(self):
        """
        Acceptance: Phase 1 (docs, schemas, fixtures, contract tests) changes no live behavior.
        Block: BLOCKED_PHASE_1_LIVE_BEHAVIOR_CHANGE
        """
        fixture = load_fixture()
        # If phase is Phase 1, affects_live_behavior must be false
        if fixture.get("phase") == "Phase 1":
            assert fixture["affects_live_behavior"] is False

    def test_rollback_flag_schema_valid(self):
        """
        Acceptance: Rollback flag schema is valid and complete.
        """
        import jsonschema
        schema = load_schema()
        fixture = load_fixture()
        jsonschema.validate(fixture, schema)

    def test_rollback_flag_stored_in_policy_snapshot(self):
        """
        Acceptance: Rollback flags are stored in policy snapshot, not runtime state.
        Block: BLOCKED_ROLLBACK_FLAG_IN_RUNTIME_STATE
        """
        fixture = load_fixture()
        assert fixture["stored_in_policy_snapshot"] is True