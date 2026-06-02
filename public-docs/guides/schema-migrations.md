# Schema Migrations

When Relic bumps its SQLite schema or you decide to move from SQLite to Postgres.

## Default behavior: SQLite, auto-migrate on startup

`~/.relic/relic.db` is a plain SQLite file. Migrations live under `relic/db/migrations/` as numbered SQL files (`0001_initial.sql`, `0002_control_incident.sql`, …). On every `relic` invocation the loader checks the `schema_version` table and applies any pending migrations in order.

You do **not** need to run migrations by hand for routine upgrades. `git pull && pip install -e . && relic runtime doctor` is the procedure.

```bash
# Procedure for a regular upgrade.
cp ~/.relic/relic.db ~/.relic/backups/relic.db.$(date +%Y%m%dT%H%M%S)
git pull
pip install -e .
relic runtime doctor    # this applies pending migrations as a side effect
```

The backup is non-optional. Migrations are usually safe, but a misaligned upgrade should not leave you without an exit.

## Migration log

Every applied migration writes a row to `schema_version`:

```sql
sqlite3 ~/.relic/relic.db "SELECT version, applied_at FROM schema_version ORDER BY version;"
```

Output looks like:

```
0001|2026-04-02 10:01:23
0002|2026-04-02 10:01:23
0003|2026-04-15 18:42:01
...
```

If the `schema_version` table is missing, you are on a pre-0001 install or the file is corrupted. Restore the last backup.

## When a migration fails

The loader stops at the first failing migration and aborts. The DB is left at the last successfully applied version. Do **not** manually `INSERT` into `schema_version`; that bypasses the schema state the application expects.

Recovery:

```bash
# 1. Capture the error from the failed run.
RELIC_LOG_LEVEL=DEBUG relic runtime doctor 2>&1 | tee migration-error.log

# 2. Restore the backup taken before the upgrade.
cp ~/.relic/backups/relic.db.<timestamp> ~/.relic/relic.db

# 3. File an issue with the migration error log. Do not edit the SQL by hand.
```

## SQLite → Postgres

The Postgres migration path lives under `migrations/sqlite_to_postgres/`. Files:

| File | Purpose |
|---|---|
| `001_initial_schema.sql` | Create the Postgres schema (subjects, gumi_instances, hermes_profiles, …). |
| `002_backfill_cascade.sql` | Backfill cascading FKs from SQLite export. |
| `003_verify_replication.sql` | Row-count and integrity verification. |
| `rollback_001_initial_schema.sql` | Undo step 1. |
| `rollback_002_backfill_cascade.sql` | Undo step 2. |

!!! warning "Not tested at production scale"
    The Postgres path is provided as an integration starting point. It has been exercised on synthetic data, not on production workloads of more than a few hundred subjects. Validate against your own dataset before committing.

### Procedure

```bash
# 1. Snapshot SQLite.
cp ~/.relic/relic.db /tmp/relic.sqlite.bak

# 2. Provision Postgres 14+ with a dedicated database, e.g. `relic`.
createdb relic

# 3. Apply the Postgres schema.
psql -d relic -f migrations/sqlite_to_postgres/001_initial_schema.sql

# 4. Export SQLite rows to CSV (one table at a time). Example for `subjects`:
sqlite3 -header -csv /tmp/relic.sqlite.bak \
  "SELECT * FROM subjects;" > /tmp/subjects.csv

# 5. Load into Postgres.
psql -d relic -c "\copy subjects FROM '/tmp/subjects.csv' WITH CSV HEADER"

# 6. Cascade fix-ups.
psql -d relic -f migrations/sqlite_to_postgres/002_backfill_cascade.sql

# 7. Verify.
psql -d relic -f migrations/sqlite_to_postgres/003_verify_replication.sql
```

The verification script reports row counts and integrity checks; review every assertion before pointing the application at Postgres.

### Point Relic at Postgres

There is no built-in Postgres adapter in the runtime as of this writing, the SQL is the integration path, not a switchable backend. Wiring the runtime to Postgres requires writing a thin adapter for `relic/persistence.py` and pointing `RELIC_DB_PATH` (or its replacement) at the Postgres URL. Plan engineering time accordingly.

### Rollback

```bash
psql -d relic -f migrations/sqlite_to_postgres/rollback_002_backfill_cascade.sql
psql -d relic -f migrations/sqlite_to_postgres/rollback_001_initial_schema.sql
dropdb relic
# Continue using SQLite from the backup.
```

## Bumping the schema yourself

If you fork Relic and add a column or table:

1. Add a new file `relic/db/migrations/00NN_<description>.sql`.
2. Make the SQL idempotent (`CREATE TABLE IF NOT EXISTS`, `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` via a guard `SELECT`, etc.).
3. End the file with `INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES ('00NN', CURRENT_TIMESTAMP);`.
4. Add a contract test under `tests/data-model/` to lock the new shape.
5. Document the change in `CHANGELOG.md`.

Never edit a published migration in place; that breaks already-migrated installs. Add a new migration that performs the additional change.

## When you have stale fixtures after a bump

Fixtures pinned to an old schema may not load. The eval harness flags them:

```bash
python scripts/eval_run.py --module data_model
```

Update the fixture, then commit the new version under a bumped path (e.g. `fixtures/data-model/v2/...`).
