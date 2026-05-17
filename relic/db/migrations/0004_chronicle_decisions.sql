-- Chronicle decisions table
-- Version: 0004
-- Schema: chronicle-decision/v1
-- Reference: docs/chronicle/agentic-development-plan.md §6.2

CREATE TABLE IF NOT EXISTS chronicle_decisions (
    decision_id            TEXT PRIMARY KEY,
    trace_id               TEXT NOT NULL,
    run_id                 TEXT,
    session_id             TEXT,
    subject_id             TEXT,
    actor_type             TEXT,
    actor_id               TEXT,
    decision_kind          TEXT NOT NULL,
    selected_action        TEXT NOT NULL,
    rejected_alternatives  TEXT DEFAULT '[]',
    observable_inputs      TEXT DEFAULT '{}',
    observable_outputs     TEXT DEFAULT '{}',
    confidence             REAL,
    uncertainty_notes      TEXT,
    evidence_refs          TEXT DEFAULT '[]',
    rationale_summary      TEXT,
    consent_basis          TEXT,
    sensitivity            TEXT NOT NULL DEFAULT 'SAFE',
    validation_status      TEXT NOT NULL DEFAULT 'pending',
    timestamp              TEXT NOT NULL,
    schema_version         TEXT NOT NULL DEFAULT 'chronicle-decision/v1',
    created_at             TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_chronicle_decisions_trace    ON chronicle_decisions(trace_id);
CREATE INDEX IF NOT EXISTS idx_chronicle_decisions_session  ON chronicle_decisions(session_id);
CREATE INDEX IF NOT EXISTS idx_chronicle_decisions_subject  ON chronicle_decisions(subject_id);
CREATE INDEX IF NOT EXISTS idx_chronicle_decisions_kind     ON chronicle_decisions(decision_kind);
CREATE INDEX IF NOT EXISTS idx_chronicle_decisions_actor    ON chronicle_decisions(actor_id);
CREATE INDEX IF NOT EXISTS idx_chronicle_decisions_status   ON chronicle_decisions(validation_status);

INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES ('0004', CURRENT_TIMESTAMP);
