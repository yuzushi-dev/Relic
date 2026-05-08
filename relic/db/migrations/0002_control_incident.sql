-- Schema update for PR07: Security and control
-- Version: 0002

-- Pause records for session pause/resume
CREATE TABLE IF NOT EXISTS pause_records (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    initiated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resumed_at TIMESTAMP,
    session_id TEXT,
    state TEXT NOT NULL DEFAULT 'paused',
    reason TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_pause_session ON pause_records(session_id);

-- Incident reports for security and privacy events
CREATE TABLE IF NOT EXISTS incident_reports (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    severity TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    session_id TEXT,
    metadata_json TEXT DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_incident_status ON incident_reports(status);
CREATE INDEX IF NOT EXISTS idx_incident_severity ON incident_reports(severity);

-- Quarantined artifacts linked to incidents
CREATE TABLE IF NOT EXISTS quarantined_artifacts (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    incident_id TEXT NOT NULL,
    artifact_type TEXT NOT NULL,
    artifact_hash TEXT NOT NULL,
    quarantined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reason TEXT NOT NULL,
    session_id TEXT,
    FOREIGN KEY (incident_id) REFERENCES incident_reports(id)
);

CREATE INDEX IF NOT EXISTS idx_quarantine_incident ON quarantined_artifacts(incident_id);

-- Prompt-Artifact relationship table
CREATE TABLE IF NOT EXISTS prompt_artifacts (
    prompt_id TEXT NOT NULL,
    artifact_id TEXT NOT NULL,
    relationship_type TEXT DEFAULT 'derived',
    PRIMARY KEY (prompt_id, artifact_id),
    FOREIGN KEY (prompt_id) REFERENCES prompt_records(id),
    FOREIGN KEY (artifact_id) REFERENCES artifact_records(id)
);

CREATE INDEX IF NOT EXISTS idx_prompt_artifact_prompt ON prompt_artifacts(prompt_id);
CREATE INDEX IF NOT EXISTS idx_prompt_artifact_artifact ON prompt_artifacts(artifact_id);

-- Record schema version
INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES ('0002', CURRENT_TIMESTAMP);
