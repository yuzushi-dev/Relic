-- Continuity Event Schema
-- Stores audit events for marker lifecycle

CREATE TABLE IF NOT EXISTS continuity_event (
    event_id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL,
    gumi_instance_id TEXT NOT NULL,
    hermes_profile_id TEXT NOT NULL,

    -- Event classification
    event_type TEXT NOT NULL CHECK (event_type IN (
        'marker_created', 'marker_confirmed', 'marker_retired', 'marker_rejected',
        'marker_expired', 'correction_created', 'correction_superseded',
        'followup_created', 'followup_sent', 'followup_acknowledged',
        'followup_ignored', 'followup_exhausted', 'followup_expired',
        'scope_paused', 'scope_resumed', 'marker_forgotten'
    )),

    -- Reference to related entity
    marker_id TEXT,
    followup_id TEXT,
    correction_id TEXT,

    -- Event data
    event_data TEXT,  -- JSON payload
    source TEXT NOT NULL CHECK (source IN ('subject', 'gumi', 'hermes_hook', 'cron', 'researcher')),
    created_at TEXT NOT NULL,

    -- Subject visibility
    subject_visible BOOLEAN NOT NULL DEFAULT FALSE,

    FOREIGN KEY (marker_id) REFERENCES continuity_marker(marker_id) ON DELETE SET NULL,
    FOREIGN KEY (followup_id) REFERENCES continuity_followup(followup_id) ON DELETE SET NULL
);

-- Index for event queries
CREATE INDEX idx_event_subject ON continuity_event(subject_id);
CREATE INDEX idx_event_type ON continuity_event(event_type);
CREATE INDEX idx_event_marker ON continuity_event(marker_id);
CREATE INDEX idx_event_created ON continuity_event(created_at);