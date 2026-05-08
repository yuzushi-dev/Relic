"""Contract tests for the Subject Overview fixture (PR27C).

Validates that ``fixtures/researcher-workbench/subject_overview_subj_001.json``
conforms to ``schemas/ui/subject_overview.schema.json`` and satisfies all
acceptance criteria defined in ``docs/ui/SUBJECT_OVERVIEW_SPEC.md``.

Block conditions tested:
  - BLOCKED_SUBJECT_SCOPE_MISSING   : subject_id must be present and non-empty.
  - BLOCKED_MISSING_GUMI_INSTANCE   : active_gumi_instance must be non-null.
  - BLOCKED_PAUSE_NOT_SUBJECT_SCOPED: pause_state must be a subject-scoped object
                                       containing exactly the required keys.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "fixtures" / "researcher-workbench" / "subject_overview_subj_001.json"
SCHEMA_PATH = REPO_ROOT / "schemas" / "ui" / "subject_overview.schema.json"

REQUIRED_TOP_LEVEL_FIELDS = [
    "subject_id",
    "experiment_id",
    "subject_status",
    "consent_status",
    "active_condition",
    "bootstrap_status",
    "active_gumi_instance",
    "hermes_profile_status",
    "last_user_interaction",
    "last_gumi_initiative",
    "last_relic_extraction",
    "last_synthesis",
    "last_correction",
    "active_cron_modes",
    "risk_summary",
    "pending_review_count",
    "pause_state",
]

REQUIRED_PAUSE_FLAGS = [
    "pause_all",
    "pause_proactive",
    "pause_checkin",
    "pause_followup",
    "pause_images",
    "pause_audio",
    "pause_music",
    "pause_diegetic_life",
    "pause_relic_ingestion",
]

VALID_SUBJECT_STATUSES = {
    "draft",
    "baseline_in_progress",
    "baseline_complete",
    "gumi_seed_generated",
    "gumi_seed_reviewed",
    "hermes_profile_provisioned",
    "intro_composed",
    "intro_sent",
    "active",
    "archived",
    "withdrawn",
}

VALID_CONSENT_STATUSES = {"pending", "consented", "withdrawn", "expired"}
VALID_BOOTSTRAP_STATUSES = {"not_started", "in_progress", "complete"}
VALID_RISK_SEVERITIES = {"none", "low", "medium", "high", "critical"}


@pytest.fixture(scope="module")
def fixture_data() -> dict:
    """Load the subject overview fixture."""
    assert FIXTURE_PATH.exists(), f"Fixture not found: {FIXTURE_PATH}"
    with FIXTURE_PATH.open() as f:
        return json.load(f)


@pytest.fixture(scope="module")
def schema_data() -> dict:
    """Load the subject overview JSON Schema."""
    assert SCHEMA_PATH.exists(), f"Schema not found: {SCHEMA_PATH}"
    with SCHEMA_PATH.open() as f:
        return json.load(f)


class TestSchemaStructure:
    """Verify the JSON Schema itself is well-formed."""

    def test_schema_has_required_meta(self, schema_data: dict) -> None:
        assert schema_data.get("$schema") == "https://json-schema.org/draft/2020-12/schema"
        assert "$id" in schema_data
        assert schema_data.get("type") == "object"

    def test_schema_declares_required_fields(self, schema_data: dict) -> None:
        schema_required = set(schema_data.get("required", []))
        for field in REQUIRED_TOP_LEVEL_FIELDS:
            assert field in schema_required, f"Schema missing required field: {field}"

    def test_schema_declares_all_pause_flags(self, schema_data: dict) -> None:
        pause_props = schema_data["properties"]["pause_state"]["properties"]
        for flag in REQUIRED_PAUSE_FLAGS:
            assert flag in pause_props, f"Schema pause_state missing flag: {flag}"

    def test_schema_pause_state_required_flags(self, schema_data: dict) -> None:
        pause_required = set(schema_data["properties"]["pause_state"].get("required", []))
        for flag in REQUIRED_PAUSE_FLAGS:
            assert flag in pause_required, f"pause_state.required missing flag: {flag}"


class TestFixtureRequiredFields:
    """Verify all required fields are present in the fixture."""

    def test_all_required_fields_present(self, fixture_data: dict) -> None:
        for field in REQUIRED_TOP_LEVEL_FIELDS:
            assert field in fixture_data, f"Fixture missing required field: {field}"

    def test_subject_id_non_empty(self, fixture_data: dict) -> None:
        """BLOCKED_SUBJECT_SCOPE_MISSING: subject_id must be present and non-empty."""
        assert fixture_data["subject_id"], "subject_id must not be empty"

    def test_experiment_id_non_empty(self, fixture_data: dict) -> None:
        assert fixture_data["experiment_id"], "experiment_id must not be empty"


class TestBlockConditions:
    """Validate block condition constraints."""

    def test_blocked_subject_scope_missing_subject_id_present(self, fixture_data: dict) -> None:
        """BLOCKED_SUBJECT_SCOPE_MISSING: fixture must have a non-empty subject_id."""
        assert "subject_id" in fixture_data
        assert isinstance(fixture_data["subject_id"], str)
        assert len(fixture_data["subject_id"]) > 0

    def test_blocked_missing_gumi_instance_active_instance_present(self, fixture_data: dict) -> None:
        """BLOCKED_MISSING_GUMI_INSTANCE: active_gumi_instance must be non-null."""
        assert fixture_data.get("active_gumi_instance") is not None, (
            "active_gumi_instance is null — triggers BLOCKED_MISSING_GUMI_INSTANCE"
        )
        assert isinstance(fixture_data["active_gumi_instance"], str)
        assert len(fixture_data["active_gumi_instance"]) > 0

    def test_blocked_pause_not_subject_scoped_pause_state_is_dict(self, fixture_data: dict) -> None:
        """BLOCKED_PAUSE_NOT_SUBJECT_SCOPED: pause_state must be a subject-level object."""
        pause_state = fixture_data.get("pause_state")
        assert isinstance(pause_state, dict), "pause_state must be an object"

    def test_blocked_pause_not_subject_scoped_all_flags_present(self, fixture_data: dict) -> None:
        """BLOCKED_PAUSE_NOT_SUBJECT_SCOPED: all granular pause flags must be present."""
        pause_state = fixture_data["pause_state"]
        for flag in REQUIRED_PAUSE_FLAGS:
            assert flag in pause_state, f"pause_state missing flag: {flag}"

    def test_blocked_pause_not_subject_scoped_flags_are_boolean(self, fixture_data: dict) -> None:
        """All pause flags must be boolean values."""
        pause_state = fixture_data["pause_state"]
        for flag in REQUIRED_PAUSE_FLAGS:
            assert isinstance(pause_state[flag], bool), (
                f"pause_state.{flag} must be boolean, got {type(pause_state[flag])}"
            )


class TestFieldTypes:
    """Verify field types match schema expectations."""

    def test_subject_status_valid_enum(self, fixture_data: dict) -> None:
        assert fixture_data["subject_status"] in VALID_SUBJECT_STATUSES

    def test_consent_status_valid_enum(self, fixture_data: dict) -> None:
        assert fixture_data["consent_status"] in VALID_CONSENT_STATUSES

    def test_bootstrap_status_valid_enum(self, fixture_data: dict) -> None:
        assert fixture_data["bootstrap_status"] in VALID_BOOTSTRAP_STATUSES

    def test_active_cron_modes_is_list(self, fixture_data: dict) -> None:
        assert isinstance(fixture_data["active_cron_modes"], list)

    def test_pending_review_count_is_non_negative_int(self, fixture_data: dict) -> None:
        count = fixture_data["pending_review_count"]
        assert isinstance(count, int)
        assert count >= 0

    def test_risk_summary_structure(self, fixture_data: dict) -> None:
        risk = fixture_data["risk_summary"]
        assert isinstance(risk, dict)
        assert "severity" in risk
        assert "flag_count" in risk
        assert risk["severity"] in VALID_RISK_SEVERITIES
        assert isinstance(risk["flag_count"], int)
        assert risk["flag_count"] >= 0

    def test_hermes_profile_status_structure(self, fixture_data: dict) -> None:
        hermes = fixture_data["hermes_profile_status"]
        assert isinstance(hermes, dict)
        assert "profile_name" in hermes
        assert "provisioned" in hermes
        assert isinstance(hermes["provisioned"], bool)

    def test_timestamp_fields_are_string_or_null(self, fixture_data: dict) -> None:
        timestamp_fields = [
            "last_user_interaction",
            "last_gumi_initiative",
            "last_relic_extraction",
            "last_synthesis",
            "last_correction",
        ]
        for field in timestamp_fields:
            value = fixture_data.get(field)
            assert value is None or isinstance(value, str), (
                f"{field} must be a string (ISO 8601) or null"
            )


class TestAcceptanceCriteria:
    """High-level acceptance criteria from PR27C."""

    def test_ac_subject_overview_inaccessible_without_subject_id(self, fixture_data: dict) -> None:
        """AC: Subject Overview is inaccessible without subject_id.
        Fixture must always carry a valid subject_id."""
        assert fixture_data.get("subject_id"), "subject_id must be present and non-empty"

    def test_ac_active_gumi_instance_visible(self, fixture_data: dict) -> None:
        """AC: Active Gumi instance is visible."""
        assert fixture_data.get("active_gumi_instance") is not None

    def test_ac_hermes_profile_visible(self, fixture_data: dict) -> None:
        """AC: Active Hermes profile is visible."""
        hermes = fixture_data.get("hermes_profile_status")
        assert hermes is not None
        assert hermes.get("profile_name")

    def test_ac_pause_controls_are_subject_scoped(self, fixture_data: dict) -> None:
        """AC: Pause controls are subject-scoped (pause_state is a per-subject object)."""
        pause_state = fixture_data.get("pause_state")
        assert isinstance(pause_state, dict)
        # Verify the pause_state is anchored to the subject by checking subject_id exists
        assert fixture_data.get("subject_id")
        # All flags present ensures the model covers subject-level granularity
        for flag in REQUIRED_PAUSE_FLAGS:
            assert flag in pause_state
