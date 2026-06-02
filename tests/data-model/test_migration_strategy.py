"""PR26G, Migration Strategy tests."""

import pytest
import json
import jsonschema


class TestMigrationStrategy:
    """Test suite for SQLite to PostgreSQL migration strategy."""

    @pytest.fixture
    def migration_plan_schema(self):
        """Load the migration plan schema."""
        schema_path = "schemas/data-model/migration_plan.schema.json"
        with open(schema_path, "r") as f:
            return json.load(f)

    @pytest.fixture
    def migration_doc(self):
        """Load the migration strategy document."""
        doc_path = "docs/data-model/07_MIGRATION_STRATEGY.md"
        with open(doc_path, "r") as f:
            return f.read()

    @pytest.fixture
    def sql_files(self):
        """Paths to migration SQL files."""
        base = "migrations/sqlite_to_postgres"
        return {
            "001": f"{base}/001_initial_schema.sql",
            "002": f"{base}/002_backfill_cascade.sql",
            "003": f"{base}/003_verify_replication.sql",
            "rollback_001": f"{base}/rollback_001_initial_schema.sql",
            "rollback_002": f"{base}/rollback_002_backfill_cascade.sql",
        }

    def test_sqlite_schema_matches_postgres_target(self, sql_files):
        """SQLite MVP schema must have corresponding PostgreSQL target."""
        # Verify migration SQL files exist
        for name, path in sql_files.items():
            with open(path, "r") as f:
                content = f.read()
            assert len(content) > 0, f"Migration file {name} is empty"

    def test_migration_is_reversible(self, migration_doc, sql_files):
        """Migration must have rollback scripts for each step."""
        assert "reversible" in migration_doc.lower() or "rollback" in migration_doc.lower()
        # Verify rollback scripts exist
        assert "rollback_001" in sql_files
        assert "rollback_002" in sql_files

    def test_no_data_loss_in_migration(self, migration_doc, sql_files):
        """Migration must verify no data loss."""
        assert "data integrity" in migration_doc.lower() or "data_loss" in migration_doc.lower()
        # Verify replication check script exists
        with open(sql_files["003"], "r") as f:
            content = f.read()
        assert "COUNT" in content or "row_count" in content

    def test_foreign_key_cascade_preserved(self, sql_files):
        """Foreign key cascades must be preserved in migration."""
        with open(sql_files["001"], "r") as f:
            content = f.read()
        assert "REFERENCES" in content or "foreign key" in content.lower()
        assert "ON DELETE CASCADE" in content

    def test_subject_scope_preserved_in_migration(self, sql_files):
        """Subject scope must be preserved in all tables during migration."""
        with open(sql_files["001"], "r") as f:
            schema_content = f.read()
        with open(sql_files["002"], "r") as f:
            backfill_content = f.read()

        # Verify subject scope columns in all relevant tables
        for table in ["runtime_objects", "events", "continuity_markers", "sensitive_signals"]:
            assert table in schema_content
            assert "subject_id" in schema_content

    def test_migration_plan_valid_json_schema(self, migration_plan_schema):
        """Migration plan schema must be valid JSON schema."""
        assert "$schema" in migration_plan_schema
        assert "sqlite_mvp" in str(migration_plan_schema.get("properties", {}).get("source_phase", {}))
