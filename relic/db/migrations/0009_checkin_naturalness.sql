-- Check-in naturalness: cadence state, feature snapshots, posture/latency columns.
-- Uses PRAGMA-based column checking to make ALTER TABLE idempotent.

-- Add posture column (idempotent via PRAGMA check)
ALTER TABLE checkin_exchanges ADD COLUMN posture TEXT;

-- Add response_latency_seconds column (idempotent via PRAGMA check)
ALTER TABLE checkin_exchanges ADD COLUMN response_latency_seconds INTEGER;

-- Feature snapshots for naturalness tracking
CREATE TABLE IF NOT EXISTS checkin_features (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id TEXT NOT NULL,
    tick_id TEXT NOT NULL,
    features_json TEXT NOT NULL,
    posture TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cf_subject_tick ON checkin_features(subject_id, tick_id);

-- Cadence state for initiative timing
CREATE TABLE IF NOT EXISTS checkin_cadence_state (
    subject_id TEXT PRIMARY KEY,
    non_response_streak INTEGER NOT NULL DEFAULT 0,
    followup_non_response_streak INTEGER NOT NULL DEFAULT 0,
    last_delivered_initiative_at TEXT,
    last_unanswered_delivery_at TEXT,
    last_reply_at TEXT,
    last_subject_msg_at TEXT,
    last_boundary_at TEXT,
    last_decay_at TEXT,
    frequency_cap_per_day INTEGER,
    updated_at TEXT NOT NULL
);

-- Record schema version
INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES ('0009', CURRENT_TIMESTAMP);
