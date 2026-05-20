-- Check-in subsystem core schema
-- Required by: 0009_checkin_naturalness.sql (adds columns to checkin_exchanges)
-- Contains: facets, traits, observations, checkin_exchanges, and supporting tables

-- Facet registry: canonical psychological dimensions
CREATE TABLE IF NOT EXISTS facets (
    id TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    spectrum_low TEXT,
    spectrum_high TEXT,
    sensitivity TEXT DEFAULT 'media',
    intrusion_base REAL DEFAULT 0.45,
    half_life_days INTEGER DEFAULT 60
);

-- Trait state: position on each facet with confidence
CREATE TABLE IF NOT EXISTS traits (
    facet_id TEXT PRIMARY KEY REFERENCES facets(id),
    value_position REAL,
    confidence REAL DEFAULT 0.0,
    observation_count INTEGER DEFAULT 0,
    last_observation_at TEXT,
    last_synthesis_at TEXT,
    status TEXT DEFAULT 'insufficient_data',
    notes TEXT
);

-- Raw observations extracted from check-in exchanges
CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    facet_id TEXT NOT NULL REFERENCES facets(id),
    source_type TEXT NOT NULL,
    source_ref TEXT,
    content TEXT NOT NULL,
    extracted_signal TEXT,
    signal_strength REAL DEFAULT 0.5,
    signal_position REAL,
    context TEXT,
    conversation_domain TEXT,
    context_metadata TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(facet_id, source_ref)
);

-- Check-in exchange log (posture/latency added in 0009_checkin_naturalness.sql)
CREATE TABLE IF NOT EXISTS checkin_exchanges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    facet_id TEXT REFERENCES facets(id),
    question_text TEXT NOT NULL,
    reply_text TEXT,
    reply_captured_at TEXT,
    observations_extracted INTEGER DEFAULT 0,
    asked_at TEXT NOT NULL,
    message_id TEXT,
    followup_sent_at TEXT
);

-- Feature snapshots for naturalness tracking
CREATE TABLE IF NOT EXISTS checkin_features (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id TEXT NOT NULL,
    tick_id TEXT NOT NULL,
    features_json TEXT NOT NULL,
    posture TEXT NOT NULL,
    created_at TEXT NOT NULL
);

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

-- Hypothesis tracking for theory refinement
CREATE TABLE IF NOT EXISTS hypotheses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hypothesis TEXT NOT NULL,
    status TEXT DEFAULT 'unverified',
    supporting_observations TEXT,
    contradicting_observations TEXT,
    confidence REAL DEFAULT 0.3,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Message inbox for async communication
CREATE TABLE IF NOT EXISTS inbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT UNIQUE,
    from_id TEXT NOT NULL,
    content TEXT NOT NULL,
    channel_id TEXT NOT NULL,
    received_at TEXT NOT NULL,
    processed INTEGER DEFAULT 0,
    processed_at TEXT
);

-- Model snapshots for temporal analysis
CREATE TABLE IF NOT EXISTS model_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_at TEXT NOT NULL,
    total_observations INTEGER,
    avg_confidence REAL,
    coverage_pct REAL,
    snapshot_data TEXT
);

-- Indexes for check-in subsystem performance
CREATE INDEX IF NOT EXISTS idx_cf_subject_tick ON checkin_features(subject_id, tick_id);
CREATE INDEX IF NOT EXISTS idx_observations_facet ON observations(facet_id);
CREATE INDEX IF NOT EXISTS idx_observations_source ON observations(source_type);
CREATE INDEX IF NOT EXISTS idx_inbox_processed ON inbox(processed);
CREATE INDEX IF NOT EXISTS idx_checkin_unprocessed ON checkin_exchanges(observations_extracted);
CREATE INDEX IF NOT EXISTS idx_checkin_pending ON checkin_exchanges(asked_at DESC) WHERE reply_text IS NULL AND facet_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_checkin_processable ON checkin_exchanges(asked_at) WHERE reply_text IS NOT NULL AND observations_extracted = 0;
CREATE INDEX IF NOT EXISTS idx_observations_source_date ON observations(source_type, created_at);
CREATE INDEX IF NOT EXISTS idx_inbox_pending ON inbox(received_at) WHERE processed = 0;

-- Record schema version
INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES ('0008', CURRENT_TIMESTAMP);
