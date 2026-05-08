-- PR33 Shared Continuity Memory - Initial Schema Migration
-- Migration: shared_continuity_001_init

BEGIN TRANSACTION;

-- Create continuity_marker table
CREATE TABLE IF NOT EXISTS continuity_marker (
    marker_id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL,
    gumi_instance_id TEXT NOT NULL,
    hermes_profile_id TEXT NOT NULL,

    -- subject_confirmation MUST be TRUE — no marker stored without subject confirmation
    subject_confirmation BOOLEAN NOT NULL CHECK (subject_confirmation = TRUE),
    source_type TEXT NOT NULL CHECK (source_type IN ('user_provided', 'user_confirmed', 'user_authored')),
    created_at TEXT NOT NULL,

    subject_words TEXT NOT NULL,
    gumi_agreed_words TEXT,
    raw_source_text TEXT,

    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'retired', 'rejected', 'expired')),
    gumi_recall_allowed BOOLEAN NOT NULL DEFAULT TRUE,

    recall_count INTEGER NOT NULL DEFAULT 0,
    max_recall_count INTEGER NOT NULL DEFAULT 3,
    ttl_seconds INTEGER NOT NULL DEFAULT 604800,

    expires_at TEXT,
    updated_at TEXT
);

-- Create continuity_followup table
CREATE TABLE IF NOT EXISTS continuity_followup (
    followup_id TEXT PRIMARY KEY,
    marker_id TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    gumi_instance_id TEXT NOT NULL,
    hermes_profile_id TEXT NOT NULL,

    max_attempts INTEGER NOT NULL DEFAULT 3,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'due', 'sent', 'acknowledged', 'ignored', 'exhausted', 'expired')),

    followup_interval_seconds INTEGER NOT NULL DEFAULT 86400,
    next_followup_at TEXT,
    ttl_seconds INTEGER NOT NULL DEFAULT 604800,
    created_at TEXT NOT NULL,
    expires_at TEXT,

    last_attempt_at TEXT,
    last_result TEXT,
    acknowledged_at TEXT,

    is_paused BOOLEAN NOT NULL DEFAULT FALSE,
    paused_at TEXT,
    resumed_at TEXT,

    FOREIGN KEY (marker_id) REFERENCES continuity_marker(marker_id) ON DELETE CASCADE
);

-- Create continuity_correction table
CREATE TABLE IF NOT EXISTS continuity_correction (
    correction_id TEXT PRIMARY KEY,
    marker_id TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    gumi_instance_id TEXT NOT NULL,
    hermes_profile_id TEXT NOT NULL,

    authoritative BOOLEAN NOT NULL DEFAULT TRUE,

    subject_words TEXT NOT NULL,
    gumi_agreed_words TEXT,
    correction_note TEXT,

    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'superseded')),
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL CHECK (created_by IN ('subject', 'gumi', 'researcher')),

    original_marker_id TEXT NOT NULL,
    is_replacement BOOLEAN NOT NULL DEFAULT TRUE,

    FOREIGN KEY (marker_id) REFERENCES continuity_marker(marker_id) ON DELETE CASCADE,
    FOREIGN KEY (original_marker_id) REFERENCES continuity_marker(marker_id) ON DELETE RESTRICT
);

-- Create continuity_event table
CREATE TABLE IF NOT EXISTS continuity_event (
    event_id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL,
    gumi_instance_id TEXT NOT NULL,
    hermes_profile_id TEXT NOT NULL,

    event_type TEXT NOT NULL CHECK (event_type IN (
        'marker_created', 'marker_confirmed', 'marker_retired', 'marker_rejected',
        'marker_expired', 'correction_created', 'correction_superseded',
        'followup_created', 'followup_sent', 'followup_acknowledged',
        'followup_ignored', 'followup_exhausted', 'followup_expired',
        'scope_paused', 'scope_resumed', 'marker_forgotten'
    )),

    marker_id TEXT,
    followup_id TEXT,
    correction_id TEXT,

    event_data TEXT,
    source TEXT NOT NULL CHECK (source IN ('subject', 'gumi', 'hermes_hook', 'cron', 'researcher')),
    created_at TEXT NOT NULL,

    subject_visible BOOLEAN NOT NULL DEFAULT FALSE,

    FOREIGN KEY (marker_id) REFERENCES continuity_marker(marker_id) ON DELETE SET NULL,
    FOREIGN KEY (followup_id) REFERENCES continuity_followup(followup_id) ON DELETE SET NULL
);

-- Create continuity_edge table
CREATE TABLE IF NOT EXISTS continuity_edge (
    edge_id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL,
    gumi_instance_id TEXT NOT NULL,
    hermes_profile_id TEXT NOT NULL,

    edge_type TEXT NOT NULL CHECK (edge_type IN (
        'corrects', 'extends', 'supersedes', 'related_to', 'reminds_of'
    )),
    source_marker_id TEXT NOT NULL,
    target_marker_id TEXT NOT NULL,

    confidence REAL NOT NULL DEFAULT 1.0 CHECK (confidence >= 0.0 AND confidence <= 1.0),
    edge_note TEXT,
    created_at TEXT NOT NULL,

    FOREIGN KEY (source_marker_id) REFERENCES continuity_marker(marker_id) ON DELETE CASCADE,
    FOREIGN KEY (target_marker_id) REFERENCES continuity_marker(marker_id) ON DELETE CASCADE
);

-- Create continuity_scope table
CREATE TABLE IF NOT EXISTS continuity_scope (
    scope_id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL,
    gumi_instance_id TEXT NOT NULL,
    hermes_profile_id TEXT NOT NULL,

    scope_type TEXT NOT NULL CHECK (scope_type IN ('global', 'topic', 'relationship', 'custom')),
    scope_name TEXT NOT NULL,
    scope_description TEXT,

    default_ttl_seconds INTEGER NOT NULL DEFAULT 604800,
    default_max_recall INTEGER NOT NULL DEFAULT 5,
    max_markers_per_scope INTEGER,

    is_paused BOOLEAN NOT NULL DEFAULT FALSE,
    is_opted_out BOOLEAN NOT NULL DEFAULT FALSE,
    paused_at TEXT,
    resumed_at TEXT,
    opted_out_at TEXT,

    created_at TEXT NOT NULL,
    updated_at TEXT,

    UNIQUE(subject_id, gumi_instance_id, hermes_profile_id, scope_name)
);

-- Create indexes
CREATE INDEX idx_marker_subject ON continuity_marker(subject_id);
CREATE INDEX idx_marker_gumi_instance ON continuity_marker(gumi_instance_id);
CREATE INDEX idx_marker_hermes_profile ON continuity_marker(hermes_profile_id);
CREATE INDEX idx_marker_status ON continuity_marker(status);
CREATE INDEX idx_marker_subject_scope ON continuity_marker(subject_id, gumi_instance_id, hermes_profile_id);

CREATE INDEX idx_followup_subject ON continuity_followup(subject_id);
CREATE INDEX idx_followup_marker ON continuity_followup(marker_id);
CREATE INDEX idx_followup_status ON continuity_followup(status);
CREATE INDEX idx_followup_next ON continuity_followup(next_followup_at) WHERE status = 'due';

CREATE INDEX idx_correction_marker ON continuity_correction(marker_id);
CREATE INDEX idx_correction_original ON continuity_correction(original_marker_id);
CREATE INDEX idx_correction_subject ON continuity_correction(subject_id);

CREATE INDEX idx_event_subject ON continuity_event(subject_id);
CREATE INDEX idx_event_type ON continuity_event(event_type);
CREATE INDEX idx_event_marker ON continuity_event(marker_id);
CREATE INDEX idx_event_created ON continuity_event(created_at);

CREATE INDEX idx_edge_subject ON continuity_edge(subject_id);
CREATE INDEX idx_edge_source ON continuity_edge(source_marker_id);
CREATE INDEX idx_edge_target ON continuity_edge(target_marker_id);
CREATE INDEX idx_edge_type ON continuity_edge(edge_type);

CREATE INDEX idx_scope_subject ON continuity_scope(subject_id);
CREATE INDEX idx_scope_name ON continuity_scope(scope_name);
CREATE INDEX idx_scope_paused ON continuity_scope(is_paused) WHERE is_paused = TRUE;

-- Insert version record
CREATE TABLE IF NOT EXISTS schema_version (
    version_id TEXT PRIMARY KEY,
    migration_name TEXT NOT NULL,
    applied_at TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('up', 'down'))
);

INSERT INTO schema_version (version_id, migration_name, applied_at, direction)
VALUES ('shared_continuity_001', 'init', datetime('now'), 'up');

COMMIT;