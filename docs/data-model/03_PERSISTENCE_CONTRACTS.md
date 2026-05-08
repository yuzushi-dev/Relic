# Persistence Contracts

## Objective

Define SQLite MVP and PostgreSQL migration contracts for all Relic/Gumi/Hermes persistence.

## Storage Strategy

| Phase | Technology | Purpose |
|-------|------------|---------|
| MVP | SQLite | Initial local storage, zero-configuration |
| Target | PostgreSQL | Production scale, concurrent access |

## SQLite MVP Contract

### Schema Overview

```
subjects
  ├── id (TEXT PRIMARY KEY)
  ├── study_id (TEXT)
  └── created_at (TEXT)

gumi_instances
  ├── id (TEXT PRIMARY KEY)
  ├── subject_id (TEXT REFERENCES subjects)
  └── created_at (TEXT)

hermes_profiles
  ├── id (TEXT PRIMARY KEY)
  ├── gumi_instance_id (TEXT REFERENCES gumi_instances)
  ├── profile_hash (TEXT)
  └── created_at (TEXT)

runtime_objects
  ├── id (TEXT PRIMARY KEY)
  ├── subject_id (TEXT NOT NULL)
  ├── gumi_instance_id (TEXT NOT NULL)
  ├── hermes_profile_id (TEXT NOT NULL)
  ├── object_type (TEXT)
  └── created_at (TEXT)

events
  ├── id (TEXT PRIMARY KEY)
  ├── subject_id (TEXT NOT NULL)
  ├── gumi_instance_id (TEXT NOT NULL)
  ├── hermes_profile_id (TEXT NOT NULL)
  ├── event_class (TEXT)
  ├── ontological_class (TEXT)
  └── timestamp (TEXT)

continuity_markers
  ├── id (TEXT PRIMARY KEY)
  ├── subject_id (TEXT NOT NULL)
  ├── gumi_instance_id (TEXT NOT NULL)
  ├── hermes_profile_id (TEXT NOT NULL)
  ├── confirmed (INTEGER DEFAULT 0)
  └── created_at (TEXT)

sensitive_signals
  ├── id (TEXT PRIMARY KEY)
  ├── subject_id (TEXT NOT NULL)
  ├── gumi_instance_id (TEXT NOT NULL)
  ├── hermes_profile_id (TEXT NOT NULL)
  └── created_at (TEXT)
```

## PostgreSQL Migration Target

### Schema Differences

| SQLite | PostgreSQL |
|--------|------------|
| TEXT | VARCHAR(255) or TEXT |
| INTEGER | BOOLEAN or INTEGER |
| No native UUID | UUID type |
| No array support | JSONB or ARRAY |
| No foreign key enforcement | FULL FK enforcement |

### Transformation Steps

1. Export SQLite data to JSON
2. Create PostgreSQL schema with UUID primary keys
3. Transform TEXT fields to appropriate PostgreSQL types
4. Import data with FK validation
5. Verify row counts match

### Rollback Procedure

1. Export PostgreSQL data to JSON
2. Drop PostgreSQL tables
3. Recreate SQLite schema
4. Import JSON data

## Constraints

1. **Vector index is NOT source of truth** - Vector embeddings are derived from canonical data.
2. **Hindsight is NOT source of truth** - Analysis tools are derived from canonical data.
3. **Subject scope must be preserved** - All tables maintain subject_id, gumi_instance_id, hermes_profile_id.

## Block Conditions

| Block ID | Condition |
|----------|-----------|
| BLOCKED_VECTOR_INDEX_AS_SOURCE_OF_TRUTH | Vector index treated as authoritative |
| BLOCKED_HINDSIGHT_AS_SOURCE_OF_TRUTH | Hindsight treated as authoritative |
| BLOCKED_MISSING_PERSISTENCE_CONTRACT | No persistence contract defined |
| BLOCKED_MISSING_POSTGRES_MIGRATION_TARGET | PostgreSQL target not documented |
