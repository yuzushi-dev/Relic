-- Durable Shared Continuity persistence
-- Version: 0013

CREATE TABLE IF NOT EXISTS continuity_marker (
    marker_id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL,
    gumi_instance_id TEXT NOT NULL,
    hermes_profile_id TEXT NOT NULL,
    subject_confirmation INTEGER NOT NULL CHECK (subject_confirmation IN (0, 1)),
    source_type TEXT NOT NULL,
    created_at TEXT NOT NULL,
    subject_words_json TEXT NOT NULL,
    gumi_agreed_words_json TEXT NOT NULL DEFAULT '[]',
    raw_source_text TEXT,
    status TEXT NOT NULL,
    gumi_recall_allowed INTEGER NOT NULL CHECK (gumi_recall_allowed IN (0, 1)),
    recall_count INTEGER NOT NULL DEFAULT 0,
    max_recall_count INTEGER NOT NULL DEFAULT 3,
    ttl_seconds INTEGER NOT NULL DEFAULT 604800,
    expires_at TEXT,
    updated_at TEXT,
    candidate_for_confirmation INTEGER NOT NULL DEFAULT 0 CHECK (candidate_for_confirmation IN (0, 1)),
    clinical_interpretation_allowed INTEGER NOT NULL DEFAULT 0 CHECK (clinical_interpretation_allowed IN (0, 1)),
    previous_version_id TEXT,
    final_subject_words_json TEXT,
    next_version_id TEXT,
    normalized_tags_json TEXT,
    gumi_words_json TEXT,
    FOREIGN KEY (previous_version_id) REFERENCES continuity_marker(marker_id)
);

CREATE INDEX IF NOT EXISTS idx_continuity_marker_subject_scope
    ON continuity_marker(subject_id, gumi_instance_id, hermes_profile_id);
CREATE INDEX IF NOT EXISTS idx_continuity_marker_status
    ON continuity_marker(status);
CREATE INDEX IF NOT EXISTS idx_continuity_marker_confirmation
    ON continuity_marker(subject_confirmation, candidate_for_confirmation);

CREATE TABLE IF NOT EXISTS continuity_correction (
    correction_id TEXT PRIMARY KEY,
    marker_id TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    gumi_instance_id TEXT NOT NULL,
    hermes_profile_id TEXT NOT NULL,
    authoritative INTEGER NOT NULL CHECK (authoritative IN (0, 1)),
    subject_words_json TEXT NOT NULL,
    gumi_agreed_words_json TEXT NOT NULL DEFAULT '[]',
    correction_note TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL,
    original_marker_id TEXT NOT NULL,
    is_replacement INTEGER NOT NULL CHECK (is_replacement IN (0, 1)),
    FOREIGN KEY (marker_id) REFERENCES continuity_marker(marker_id) ON DELETE CASCADE,
    FOREIGN KEY (original_marker_id) REFERENCES continuity_marker(marker_id)
);

CREATE INDEX IF NOT EXISTS idx_continuity_correction_subject
    ON continuity_correction(subject_id);
CREATE INDEX IF NOT EXISTS idx_continuity_correction_original
    ON continuity_correction(original_marker_id);

CREATE TABLE IF NOT EXISTS continuity_scope (
    scope_key TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL,
    gumi_instance_id TEXT,
    hermes_profile_id TEXT,
    scope_name TEXT NOT NULL,
    is_paused INTEGER NOT NULL DEFAULT 0 CHECK (is_paused IN (0, 1)),
    paused_at TEXT,
    resumed_at TEXT,
    scope_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_continuity_scope_subject
    ON continuity_scope(subject_id);
CREATE INDEX IF NOT EXISTS idx_continuity_scope_paused
    ON continuity_scope(is_paused) WHERE is_paused = 1;

CREATE TABLE IF NOT EXISTS continuity_event (
    sequence_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    subject_id TEXT NOT NULL,
    gumi_instance_id TEXT NOT NULL,
    hermes_profile_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    marker_id TEXT,
    followup_id TEXT,
    correction_id TEXT,
    event_data_json TEXT NOT NULL DEFAULT '{}',
    source TEXT NOT NULL,
    created_at TEXT NOT NULL,
    subject_visible INTEGER NOT NULL DEFAULT 0 CHECK (subject_visible IN (0, 1))
);

CREATE INDEX IF NOT EXISTS idx_continuity_event_subject
    ON continuity_event(subject_id);
CREATE INDEX IF NOT EXISTS idx_continuity_event_marker
    ON continuity_event(marker_id);
CREATE INDEX IF NOT EXISTS idx_continuity_event_type
    ON continuity_event(event_type);

INSERT OR REPLACE INTO schema_version (version, applied_at)
VALUES ('0013', CURRENT_TIMESTAMP);
