-- Continuity Edge Schema
-- Stores relationships between markers for relational memory

CREATE TABLE IF NOT EXISTS continuity_edge (
    edge_id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL,
    gumi_instance_id TEXT NOT NULL,
    hermes_profile_id TEXT NOT NULL,

    -- Edge definition
    edge_type TEXT NOT NULL CHECK (edge_type IN (
        'corrects', 'extends', 'supersedes', 'related_to', 'reminds_of'
    )),
    source_marker_id TEXT NOT NULL,
    target_marker_id TEXT NOT NULL,

    -- Edge metadata
    confidence REAL NOT NULL DEFAULT 1.0 CHECK (confidence >= 0.0 AND confidence <= 1.0),
    edge_note TEXT,
    created_at TEXT NOT NULL,

    FOREIGN KEY (source_marker_id) REFERENCES continuity_marker(marker_id) ON DELETE CASCADE,
    FOREIGN KEY (target_marker_id) REFERENCES continuity_marker(marker_id) ON DELETE CASCADE
);

-- Index for edge queries
CREATE INDEX idx_edge_subject ON continuity_edge(subject_id);
CREATE INDEX idx_edge_source ON continuity_edge(source_marker_id);
CREATE INDEX idx_edge_target ON continuity_edge(target_marker_id);
CREATE INDEX idx_edge_type ON continuity_edge(edge_type);