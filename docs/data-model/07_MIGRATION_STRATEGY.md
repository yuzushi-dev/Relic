# Migration Strategy: SQLite to PostgreSQL

## Objective

Define migration strategy from SQLite MVP to PostgreSQL for all Relic/Gumi/Hermes persistence, ensuring reversibility, data integrity, and no disruption to live subjects.

## Migration Principles

1. **Reversibility** — Each migration step has a corresponding rollback script
2. **Data Integrity** — No data loss during migration
3. **Subject Scope Preserved** — All subject-scoped data maintains its scope
4. **Foreign Key Cascades** — FK relationships preserved from SQLite to PostgreSQL
5. **No Production Disruption** — Live subjects are never affected

## Migration Steps

### Step 1: Initial Schema Migration (001_initial_schema.sql)

Create PostgreSQL schema matching SQLite structure:

```sql
-- Create tables with UUID primary keys
-- Preserve TEXT types where compatible
-- Add explicit foreign key constraints
```

### Step 2: Backfill and Cascade (002_backfill_cascade.sql)

Migrate data from SQLite to PostgreSQL:

```sql
-- Export SQLite data to intermediate JSON
-- Transform data types (TEXT -> UUID where appropriate)
-- Backfill all tables preserving FK relationships
-- Verify row counts match
```

### Step 3: Verify Replication (003_verify_replication.sql)

Verify data integrity after migration:

```sql
-- Compare row counts between SQLite and PostgreSQL
-- Verify foreign key relationships
-- Check subject scope preservation
-- Validate data integrity constraints
```

## Rollback Procedures

### Rollback 001_initial_schema.sql

Drop PostgreSQL tables and recreate SQLite schema.

### Rollback 002_backfill_cascade.sql

Re-import data from SQLite backup into PostgreSQL, then proceed with rollback 001.

## Constraints

1. **Vector index is NOT source of truth** — Vector embeddings are derived from canonical data
2. **Subject scope is preserved** — All tables maintain subject_id, gumi_instance_id, hermes_profile_id
3. **Foreign key cascades are preserved** — No FK relationship is lost in migration
4. **Migration is reversible** — Each step can be rolled back

## Block Conditions

| Block ID | Condition |
|----------|-----------|
| BLOCKED_IRREVERSIBLE_MIGRATION | Migration cannot be rolled back |
| BLOCKED_MISSING_MIGRATION_PLAN | No migration plan documented |
| BLOCKED_FOREIGN_KEY_LOSS_IN_MIGRATION | FK relationships lost |
| BLOCKED_SUBJECT_SCOPE_LOST_IN_MIGRATION | Subject scope not preserved |
| BLOCKED_VECTOR_INDEX_AS_PRIMARY_STORE | Vector index treated as authoritative |
