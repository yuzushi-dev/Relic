-- Continuity Marker Schema
-- Stores user-confirmed continuity markers with subject scope

CREATE TABLE IF NOT EXISTS continuity_marker (
    marker_id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL,
    gumi_instance_id TEXT NOT NULL,
    hermes_profile_id TEXT NOT NULL,

    -- Confirmation and source
    -- subject_confirmation MUST be TRUE — no marker stored without subject confirmation
    subject_confirmation BOOLEAN NOT NULL CHECK (subject_confirmation = TRUE),
    source_type TEXT NOT NULL CHECK (source_type IN ('user_provided', 'user_confirmed', 'user_authored')),
    created_at TEXT NOT NULL,

    -- Content
    subject_words TEXT NOT NULL,
    gumi_agreed_words TEXT,
    raw_source_text TEXT,

    -- Status and lifecycle
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'retired', 'rejected', 'expired')),
    gumi_recall_allowed BOOLEAN NOT NULL DEFAULT TRUE,

    -- Recall limits
    recall_count INTEGER NOT NULL DEFAULT 0,
    max_recall_count INTEGER NOT NULL DEFAULT 3,
    ttl_seconds INTEGER NOT NULL DEFAULT 604800,  -- 7 days default

    -- Timestamps
    expires_at TEXT,
    updated_at TEXT
);

-- Index for subject-scoped queries
CREATE INDEX idx_marker_subject ON continuity_marker(subject_id);
CREATE INDEX idx_marker_gumi_instance ON continuity_marker(gumi_instance_id);
CREATE INDEX idx_marker_hermes_profile ON continuity_marker(hermes_profile_id);
CREATE INDEX idx_marker_status ON continuity_marker(status);

-- Ensure subject scope is always required
CREATE INDEX idx_marker_subject_scope ON continuity_marker(subject_id, gumi_instance_id, hermes_profile_id);