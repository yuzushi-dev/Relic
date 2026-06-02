"""PR26C, Persistence Contracts tests."""

import pytest
import json
import jsonschema


class TestPersistenceContracts:
    """Test suite for persistence contracts."""

    @pytest.fixture
    def persistence_contract_schema(self):
        """Load the persistence contract schema."""
        schema_path = "schemas/data-model/persistence_contract.schema.json"
        with open(schema_path, "r") as f:
            return json.load(f)

    @pytest.fixture
    def sqlite_mvp_contract(self):
        """Load the SQLite MVP contract."""
        fixture_path = "fixtures/data-model/persistence_contract_sqlite_mvp.json"
        with open(fixture_path, "r") as f:
            return json.load(f)

    @pytest.fixture
    def postgres_target_contract(self):
        """Load the PostgreSQL target contract."""
        fixture_path = "fixtures/data-model/persistence_contract_postgres_target.json"
        with open(fixture_path, "r") as f:
            return json.load(f)

    def test_sqlite_mvp_documented(self, sqlite_mvp_contract, persistence_contract_schema):
        """SQLite MVP must be documented."""
        assert sqlite_mvp_contract["storage_phase"] == "sqlite_mvp"
        jsonschema.validate(sqlite_mvp_contract, persistence_contract_schema)

    def test_postgres_migration_documented(self, postgres_target_contract, persistence_contract_schema):
        """PostgreSQL migration target must be documented."""
        assert postgres_target_contract["storage_phase"] == "postgres_target"
        jsonschema.validate(postgres_target_contract, persistence_contract_schema)

    def test_vector_index_not_source_of_truth(self, sqlite_mvp_contract, postgres_target_contract):
        """Vector index must not be treated as source of truth."""
        assert sqlite_mvp_contract["constraints"]["vector_index_not_source_of_truth"] is True
        assert postgres_target_contract["constraints"]["vector_index_not_source_of_truth"] is True

    def test_hindsight_not_source_of_truth(self, sqlite_mvp_contract, postgres_target_contract):
        """Hindsight must not be treated as source of truth."""
        assert sqlite_mvp_contract["constraints"]["hindsight_not_source_of_truth"] is True
        assert postgres_target_contract["constraints"]["hindsight_not_source_of_truth"] is True

    def test_persistence_contract_valid_schema(self, sqlite_mvp_contract, persistence_contract_schema):
        """Persistence contract must be valid against schema."""
        jsonschema.validate(sqlite_mvp_contract, persistence_contract_schema)

    def test_subject_scope_preserved_in_sqlite(self, sqlite_mvp_contract):
        """Subject scope must be preserved in SQLite MVP."""
        for table in sqlite_mvp_contract["tables"]:
            if table["name"] in ["runtime_objects", "events", "continuity_markers", "sensitive_signals"]:
                columns = [c["name"] for c in table["columns"]]
                assert "subject_id" in columns
                assert "gumi_instance_id" in columns
                assert "hermes_profile_id" in columns

    def test_subject_scope_preserved_in_postgres(self, postgres_target_contract):
        """Subject scope must be preserved in PostgreSQL target."""
        for table in postgres_target_contract["tables"]:
            if table["name"] in ["runtime_objects", "events", "continuity_markers", "sensitive_signals"]:
                columns = [c["name"] for c in table["columns"]]
                assert "subject_id" in columns
                assert "gumi_instance_id" in columns
                assert "hermes_profile_id" in columns
