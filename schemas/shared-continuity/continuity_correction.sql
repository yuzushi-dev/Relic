-- Continuity Correction Schema
-- Stores corrections to markers as authoritative replacements

CREATE TABLE IF NOT EXISTS continuity_correction (
    correction_id TEXT PRIMARY KEY,
    marker_id TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    gumi_instance_id TEXT NOT NULL,
    hermes_profile_id TEXT NOT NULL,

    -- Authoritative flag
    authoritative BOOLEAN NOT NULL DEFAULT TRUE,

    -- Correction content
    subject_words TEXT NOT NULL,
    gumi_agreed_words TEXT,
    correction_note TEXT,

    -- Lifecycle
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'superseded')),
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL CHECK (created_by IN ('subject', 'gumi', 'researcher')),

    -- Relationship to original
    original_marker_id TEXT NOT NULL,
    is_replacement BOOLEAN NOT NULL DEFAULT TRUE,

    FOREIGN KEY (marker_id) REFERENCES continuity_marker(marker_id) ON DELETE CASCADE,
    FOREIGN KEY (original_marker_id) REFERENCES continuity_marker(marker_id) ON DELETE RESTRICT
);

-- Index for correction lookups
CREATE INDEX idx_correction_marker ON continuity_correction(marker_id);
CREATE INDEX idx_correction_original ON continuity_correction(original_marker_id);
CREATE INDEX idx_correction_subject ON continuity_correction(subject_id);