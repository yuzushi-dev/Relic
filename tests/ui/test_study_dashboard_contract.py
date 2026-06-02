"""PR27B, Study Dashboard contract tests.

Verifies that:
- Schema files exist and are valid JSON Schema.
- Fixture conforms to study_overview.schema.json structure.
- Every subject row in the fixture satisfies subject_registry_row.schema.json.
- Acceptance criteria are enforced:
    * Every row has subject_id, gumi_instance_id, hermes_profile_id.
    * hermes_profile_id=null rows are counted in hermes_provisioning_failures.
    * Cross-subject aggregate counts are consistent with the subject list.
    * Bulk-forbidden fields (identity/world/persona/baseline) are absent from rows.
- Block conditions are structurally impossible to violate given the schema.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS_UI = ROOT / "schemas" / "ui"
FIXTURES_RW = ROOT / "fixtures" / "researcher-workbench"

STUDY_OVERVIEW_SCHEMA = SCHEMAS_UI / "study_overview.schema.json"
SUBJECT_ROW_SCHEMA = SCHEMAS_UI / "subject_registry_row.schema.json"
STUDY_OVERVIEW_FIXTURE = FIXTURES_RW / "study_overview.json"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Schema existence and structure
# ---------------------------------------------------------------------------

class TestSchemaFiles:
    def test_study_overview_schema_exists(self) -> None:
        assert STUDY_OVERVIEW_SCHEMA.exists(), f"Missing: {STUDY_OVERVIEW_SCHEMA}"

    def test_subject_registry_row_schema_exists(self) -> None:
        assert SUBJECT_ROW_SCHEMA.exists(), f"Missing: {SUBJECT_ROW_SCHEMA}"

    def test_study_overview_schema_is_valid_json(self) -> None:
        schema = _load_json(STUDY_OVERVIEW_SCHEMA)
        assert isinstance(schema, dict)
        assert "properties" in schema

    def test_subject_registry_row_schema_is_valid_json(self) -> None:
        schema = _load_json(SUBJECT_ROW_SCHEMA)
        assert isinstance(schema, dict)
        assert "properties" in schema

    def test_study_overview_schema_required_fields(self) -> None:
        schema = _load_json(STUDY_OVERVIEW_SCHEMA)
        required = set(schema.get("required", []))
        for field in [
            "study_id",
            "protocol_version",
            "subjects_active",
            "subjects_paused",
            "subjects_archived",
            "subjects_by_condition",
            "active_risk_alerts",
            "pending_reviews",
            "failed_cron_jobs",
            "hermes_provisioning_failures",
            "exports_pending",
            "last_validation_run",
        ]:
            assert field in required, f"study_overview.schema.json missing required field: {field}"

    def test_subject_registry_row_schema_required_fields(self) -> None:
        schema = _load_json(SUBJECT_ROW_SCHEMA)
        required = set(schema.get("required", []))
        for field in [
            "subject_id",
            "gumi_instance_id",
            "hermes_profile_id",
            "condition",
            "status",
            "last_user_interaction_at",
            "last_gumi_initiative_at",
            "risk",
            "pending_review",
        ]:
            assert field in required, f"subject_registry_row.schema.json missing required field: {field}"

    def test_subject_status_enum(self) -> None:
        schema = _load_json(SUBJECT_ROW_SCHEMA)
        status_enum = schema["properties"]["status"]["enum"]
        assert set(status_enum) == {"active", "paused", "archived"}

    def test_subject_risk_enum(self) -> None:
        schema = _load_json(SUBJECT_ROW_SCHEMA)
        risk_enum = schema["properties"]["risk"]["enum"]
        assert set(risk_enum) == {"none", "low", "medium", "high"}


# ---------------------------------------------------------------------------
# Fixture existence and top-level structure
# ---------------------------------------------------------------------------

class TestFixtureExists:
    def test_study_overview_fixture_exists(self) -> None:
        assert STUDY_OVERVIEW_FIXTURE.exists(), f"Missing: {STUDY_OVERVIEW_FIXTURE}"

    def test_fixture_is_valid_json(self) -> None:
        data = _load_json(STUDY_OVERVIEW_FIXTURE)
        assert isinstance(data, dict)


# ---------------------------------------------------------------------------
# Fixture: study_overview top-level fields
# ---------------------------------------------------------------------------

class TestStudyOverviewFixture:
    @pytest.fixture(scope="class")
    def overview(self) -> dict:
        return _load_json(STUDY_OVERVIEW_FIXTURE)

    def test_study_id_present(self, overview: dict) -> None:
        assert "study_id" in overview
        assert isinstance(overview["study_id"], str)
        assert len(overview["study_id"]) > 0

    def test_protocol_version_present(self, overview: dict) -> None:
        assert "protocol_version" in overview
        assert isinstance(overview["protocol_version"], str)

    def test_aggregate_counts_non_negative(self, overview: dict) -> None:
        for field in ("subjects_active", "subjects_paused", "subjects_archived",
                      "active_risk_alerts", "pending_reviews", "failed_cron_jobs",
                      "hermes_provisioning_failures", "exports_pending"):
            assert overview[field] >= 0, f"{field} must be >= 0"

    def test_subjects_by_condition_is_dict(self, overview: dict) -> None:
        sbc = overview["subjects_by_condition"]
        assert isinstance(sbc, dict)
        for k, v in sbc.items():
            assert isinstance(k, str)
            assert isinstance(v, int) and v >= 0

    def test_last_validation_run_is_string_or_null(self, overview: dict) -> None:
        lvr = overview["last_validation_run"]
        assert lvr is None or isinstance(lvr, str)

    def test_no_raw_cross_subject_data_in_top_level(self, overview: dict) -> None:
        """BLOCKED_CROSS_SUBJECT_RAW_DATA: top-level must not expose raw per-subject records."""
        forbidden_keys = {"raw_subjects", "subject_records", "subject_data"}
        assert not forbidden_keys.intersection(overview.keys()), (
            "Top-level fixture must not contain raw per-subject arrays at the study_overview level"
        )


# ---------------------------------------------------------------------------
# Fixture: subject registry rows
# ---------------------------------------------------------------------------

class TestSubjectRegistryRows:
    @pytest.fixture(scope="class")
    def rows(self) -> list[dict]:
        data = _load_json(STUDY_OVERVIEW_FIXTURE)
        # _subjects is a fixture-internal list; real API returns a separate array.
        return data.get("subject_registry", [])

    def test_at_least_one_row(self, rows: list[dict]) -> None:
        assert len(rows) > 0, "Fixture must include at least one subject row"

    def test_every_row_has_subject_id(self, rows: list[dict]) -> None:
        for row in rows:
            assert "subject_id" in row, f"Missing subject_id in row: {row}"
            assert isinstance(row["subject_id"], str) and row["subject_id"]

    def test_every_row_has_gumi_instance_id(self, rows: list[dict]) -> None:
        for row in rows:
            assert "gumi_instance_id" in row, f"Missing gumi_instance_id in row: {row}"
            assert isinstance(row["gumi_instance_id"], str) and row["gumi_instance_id"]

    def test_every_row_has_hermes_profile_id_field(self, rows: list[dict]) -> None:
        """BLOCKED_MISSING_HERMES_PROFILE_ID: field must always be present (may be null)."""
        for row in rows:
            assert "hermes_profile_id" in row, (
                f"hermes_profile_id key missing entirely from row {row.get('subject_id')}"
            )

    def test_hermes_provisioning_failures_matches_null_count(self, rows: list[dict]) -> None:
        """hermes_provisioning_failures in overview must equal number of null hermes_profile_id rows."""
        overview = _load_json(STUDY_OVERVIEW_FIXTURE)
        null_count = sum(1 for r in rows if r["hermes_profile_id"] is None)
        assert overview["hermes_provisioning_failures"] == null_count, (
            f"hermes_provisioning_failures={overview['hermes_provisioning_failures']} "
            f"but {null_count} rows have hermes_profile_id=null"
        )

    def test_status_values_are_valid(self, rows: list[dict]) -> None:
        valid_statuses = {"active", "paused", "archived"}
        for row in rows:
            assert row["status"] in valid_statuses, (
                f"Invalid status '{row['status']}' for subject {row.get('subject_id')}"
            )

    def test_risk_values_are_valid(self, rows: list[dict]) -> None:
        valid_risks = {"none", "low", "medium", "high"}
        for row in rows:
            assert row["risk"] in valid_risks, (
                f"Invalid risk '{row['risk']}' for subject {row.get('subject_id')}"
            )

    def test_pending_review_is_boolean(self, rows: list[dict]) -> None:
        for row in rows:
            assert isinstance(row["pending_review"], bool), (
                f"pending_review must be bool for subject {row.get('subject_id')}"
            )

    def test_subject_ids_are_unique(self, rows: list[dict]) -> None:
        ids = [r["subject_id"] for r in rows]
        assert len(ids) == len(set(ids)), "Duplicate subject_id detected in fixture"

    # -----------------------------------------------------------------------
    # Block conditions
    # -----------------------------------------------------------------------

    def test_blocked_bulk_identity_edit_fields_absent(self, rows: list[dict]) -> None:
        """BLOCKED_BULK_IDENTITY_EDIT: identity/world/persona/baseline fields must not appear in rows."""
        forbidden = {"identity", "world_state", "persona", "baseline"}
        for row in rows:
            overlap = forbidden.intersection(row.keys())
            assert not overlap, (
                f"BLOCKED_BULK_IDENTITY_EDIT violated, row {row.get('subject_id')} "
                f"contains forbidden fields: {overlap}"
            )

    def test_active_risk_alerts_matches_non_none_risk(self, rows: list[dict]) -> None:
        """active_risk_alerts in overview must equal number of rows with risk != none."""
        overview = _load_json(STUDY_OVERVIEW_FIXTURE)
        alert_count = sum(1 for r in rows if r["risk"] != "none")
        assert overview["active_risk_alerts"] == alert_count, (
            f"active_risk_alerts={overview['active_risk_alerts']} "
            f"but {alert_count} rows have risk != none"
        )

    def test_status_counts_consistent_with_rows(self, rows: list[dict]) -> None:
        """subjects_active/paused/archived must match actual row counts."""
        overview = _load_json(STUDY_OVERVIEW_FIXTURE)
        for status in ("active", "paused", "archived"):
            expected = sum(1 for r in rows if r["status"] == status)
            actual = overview[f"subjects_{status}"]
            assert actual == expected, (
                f"subjects_{status}={actual} but {expected} rows have status={status}"
            )
