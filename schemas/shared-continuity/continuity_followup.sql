-- Continuity Followup Schema
-- Stores follow-up permissions and lifecycle for markers

CREATE TABLE IF NOT EXISTS continuity_followup (
    followup_id TEXT PRIMARY KEY,
    marker_id TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    gumi_instance_id TEXT NOT NULL,
    hermes_profile_id TEXT NOT NULL,

    -- Followup configuration
    max_attempts INTEGER NOT NULL DEFAULT 3,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'due', 'sent', 'acknowledged', 'ignored', 'exhausted', 'expired')),

    -- Timing
    followup_interval_seconds INTEGER NOT NULL DEFAULT 86400,  -- 1 day default
    next_followup_at TEXT,
    ttl_seconds INTEGER NOT NULL DEFAULT 604800,  -- 7 days default
    created_at TEXT NOT NULL,
    expires_at TEXT,

    -- Result tracking
    last_attempt_at TEXT,
    last_result TEXT,
    acknowledged_at TEXT,

    -- Pause support
    is_paused BOOLEAN NOT NULL DEFAULT FALSE,
    paused_at TEXT,
    resumed_at TEXT,

    FOREIGN KEY (marker_id) REFERENCES continuity_marker(marker_id) ON DELETE CASCADE
);

-- Index for subject-scoped followup queries
CREATE INDEX idx_followup_subject ON continuity_followup(subject_id);
CREATE INDEX idx_followup_marker ON continuity_followup(marker_id);
CREATE INDEX idx_followup_status ON continuity_followup(status);
CREATE INDEX idx_followup_next ON continuity_followup(next_followup_at) WHERE status = 'due';