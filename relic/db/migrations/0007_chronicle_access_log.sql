-- Chronicle access audit log
-- Version: 0007
-- Schema: chronicle-access/v1
-- Reference: docs/chronicle/agentic-development-plan.md §6.5
-- Records every researcher/researcher-mode access to Chronicle data.

CREATE TABLE IF NOT EXISTS chronicle_access_log (
    access_id              TEXT PRIMARY KEY,
    trace_id               TEXT,
    accessor_id            TEXT NOT NULL,
    access_kind           TEXT NOT NULL,
    target_filter          TEXT DEFAULT '{}',
    rows_returned          INTEGER DEFAULT 0,
    result_hash            TEXT,
    reason                 TEXT,
    ip_address             TEXT,
    user_agent             TEXT,
    timestamp              TEXT NOT NULL,
    schema_version         TEXT NOT NULL DEFAULT 'chronicle-access/v1',
    created_at             TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_chronicle_access_accessor  ON chronicle_access_log(accessor_id);
CREATE INDEX IF NOT EXISTS idx_chronicle_access_kind      ON chronicle_access_log(access_kind);
CREATE INDEX IF NOT EXISTS idx_chronicle_access_subject   ON chronicle_access_log(target_filter);
CREATE INDEX IF NOT EXISTS idx_chronicle_access_timestamp ON chronicle_access_log(timestamp);

INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES ('0007', CURRENT_TIMESTAMP);
