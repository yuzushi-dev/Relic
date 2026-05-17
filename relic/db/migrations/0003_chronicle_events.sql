-- Chronicle events table
-- Version: 0003
-- Schema: chronicle-event/v1
-- Reference: docs/chronicle/agentic-development-plan.md §6.1

CREATE TABLE IF NOT EXISTS chronicle_events (
    event_id            TEXT PRIMARY KEY,
    event_type          TEXT NOT NULL,
    event_category      TEXT NOT NULL,
    trace_id            TEXT NOT NULL,
    run_id              TEXT,
    session_id          TEXT,
    parent_event_id     TEXT,
    experiment_id       TEXT,
    subject_id          TEXT,
    agent_id            TEXT,
    profile_id          TEXT,
    hermes_profile_id   TEXT,
    actor_type          TEXT,
    actor_id            TEXT,
    source_module       TEXT,
    target_module       TEXT,
    timestamp           TEXT NOT NULL,
    duration_ms         REAL,
    input_refs          TEXT DEFAULT '[]',
    output_refs         TEXT DEFAULT '[]',
    payload_redacted    INTEGER DEFAULT 0,
    payload_hash        TEXT,
    payload             TEXT DEFAULT '{}',
    sensitivity         TEXT NOT NULL DEFAULT 'safe',
    visibility          TEXT NOT NULL DEFAULT 'researcher',
    consent_basis       TEXT,
    retention_policy    TEXT NOT NULL DEFAULT 'standard_365d',
    tags                TEXT DEFAULT '[]',
    severity            TEXT NOT NULL DEFAULT 'info',
    validation_status   TEXT,
    error_code          TEXT,
    retry_count         INTEGER DEFAULT 0,
    schema_version      TEXT NOT NULL DEFAULT 'chronicle-event/v1',
    created_at          TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_chronicle_events_trace       ON chronicle_events(trace_id);
CREATE INDEX IF NOT EXISTS idx_chronicle_events_session     ON chronicle_events(session_id);
CREATE INDEX IF NOT EXISTS idx_chronicle_events_run         ON chronicle_events(run_id);
CREATE INDEX IF NOT EXISTS idx_chronicle_events_experiment ON chronicle_events(experiment_id);
CREATE INDEX IF NOT EXISTS idx_chronicle_events_subject     ON chronicle_events(subject_id);
CREATE INDEX IF NOT EXISTS idx_chronicle_events_profile     ON chronicle_events(profile_id);
CREATE INDEX IF NOT EXISTS idx_chronicle_events_type        ON chronicle_events(event_type);
CREATE INDEX IF NOT EXISTS idx_chronicle_events_category    ON chronicle_events(event_category);
CREATE INDEX IF NOT EXISTS idx_chronicle_events_timestamp   ON chronicle_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_chronicle_events_parent      ON chronicle_events(parent_event_id);
CREATE INDEX IF NOT EXISTS idx_chronicle_events_severity   ON chronicle_events(severity);
CREATE INDEX IF NOT EXISTS idx_chronicle_events_sensitivity  ON chronicle_events(sensitivity);
CREATE INDEX IF NOT EXISTS idx_chronicle_events_retention   ON chronicle_events(retention_policy);
CREATE INDEX IF NOT EXISTS idx_chronicle_events_hermes      ON chronicle_events(hermes_profile_id);

INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES ('0003', CURRENT_TIMESTAMP);
