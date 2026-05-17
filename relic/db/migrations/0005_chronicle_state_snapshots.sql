-- Chronicle state snapshots table
-- Version: 0005
-- Schema: chronicle-snapshot/v1
-- Reference: docs/chronicle/agentic-development-plan.md §6.3

CREATE TABLE IF NOT EXISTS chronicle_state_snapshots (
    snapshot_id            TEXT PRIMARY KEY,
    snapshot_type          TEXT NOT NULL,
    subject_id             TEXT,
    scope_ref              TEXT,
    trace_id               TEXT,
    captured_at            TEXT NOT NULL,
    trigger_event_id       TEXT,
    previous_snapshot_id   TEXT,
    content_hash           TEXT NOT NULL,
    content_ref            TEXT,
    content_size_bytes     INTEGER,
    diff_from_previous     TEXT,
    sensitivity            TEXT NOT NULL DEFAULT 'safe',
    retention_policy       TEXT NOT NULL DEFAULT 'standard_365d',
    schema_version         TEXT NOT NULL DEFAULT 'chronicle-snapshot/v1',
    created_at             TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_chronicle_snapshots_subject  ON chronicle_state_snapshots(subject_id);
CREATE INDEX IF NOT EXISTS idx_chronicle_snapshots_type     ON chronicle_state_snapshots(snapshot_type);
CREATE INDEX IF NOT EXISTS idx_chronicle_snapshots_ref      ON chronicle_state_snapshots(scope_ref);
CREATE INDEX IF NOT EXISTS idx_chronicle_snapshots_trace    ON chronicle_state_snapshots(trace_id);
CREATE INDEX IF NOT EXISTS idx_chronicle_snapshots_captured ON chronicle_state_snapshots(captured_at);
CREATE INDEX IF NOT EXISTS idx_chronicle_snapshots_previous ON chronicle_state_snapshots(previous_snapshot_id);
CREATE INDEX IF NOT EXISTS idx_chronicle_snapshots_retention ON chronicle_state_snapshots(retention_policy);

INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES ('0005', CURRENT_TIMESTAMP);
