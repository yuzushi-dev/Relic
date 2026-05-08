-- Continuity Scope Schema
-- Defines recall boundaries per subject

CREATE TABLE IF NOT EXISTS continuity_scope (
    scope_id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL,
    gumi_instance_id TEXT NOT NULL,
    hermes_profile_id TEXT NOT NULL,

    -- Scope definition
    scope_type TEXT NOT NULL CHECK (scope_type IN ('global', 'topic', 'relationship', 'custom')),
    scope_name TEXT NOT NULL,
    scope_description TEXT,

    -- Recall boundaries
    default_ttl_seconds INTEGER NOT NULL DEFAULT 604800,  -- 7 days
    default_max_recall INTEGER NOT NULL DEFAULT 5,
    max_markers_per_scope INTEGER,  -- NULL = unlimited

    -- Pause and opt-out
    is_paused BOOLEAN NOT NULL DEFAULT FALSE,
    is_opted_out BOOLEAN NOT NULL DEFAULT FALSE,
    paused_at TEXT,
    resumed_at TEXT,
    opted_out_at TEXT,

    -- Timestamps
    created_at TEXT NOT NULL,
    updated_at TEXT,

    UNIQUE(subject_id, gumi_instance_id, hermes_profile_id, scope_name)
);

-- Index for scope queries
CREATE INDEX idx_scope_subject ON continuity_scope(subject_id);
CREATE INDEX idx_scope_name ON continuity_scope(scope_name);
CREATE INDEX idx_scope_paused ON continuity_scope(is_paused) WHERE is_paused = TRUE;