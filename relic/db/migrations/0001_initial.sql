-- Initial schema for relic runtime governance
-- Version: 0001

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Lineage tracking base table
CREATE TABLE IF NOT EXISTS lineage_base (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Prompt records with privacy-safe storage
CREATE TABLE IF NOT EXISTS prompt_records (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    content_length INTEGER NOT NULL,
    is_redacted INTEGER DEFAULT 0,
    original_prompt_id TEXT,
    FOREIGN KEY (original_prompt_id) REFERENCES prompt_records(id)
);

CREATE INDEX IF NOT EXISTS idx_prompt_session ON prompt_records(session_id);
CREATE INDEX IF NOT EXISTS idx_prompt_hash ON prompt_records(content_hash);

-- Correction records for audit trail
CREATE TABLE IF NOT EXISTS correction_records (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    prompt_id TEXT NOT NULL,
    correction_type TEXT NOT NULL,
    delta_content TEXT NOT NULL,
    applied INTEGER DEFAULT 0,
    source TEXT DEFAULT 'manual',
    FOREIGN KEY (prompt_id) REFERENCES prompt_records(id)
);

CREATE INDEX IF NOT EXISTS idx_correction_prompt ON correction_records(prompt_id);

-- Artifact registry
CREATE TABLE IF NOT EXISTS artifact_records (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    session_id TEXT NOT NULL,
    artifact_type TEXT NOT NULL,
    artifact_hash TEXT NOT NULL,
    lineage_path TEXT DEFAULT '',
    metadata_json TEXT DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_artifact_session ON artifact_records(session_id);
CREATE INDEX IF NOT EXISTS idx_artifact_hash ON artifact_records(artifact_hash);

-- Consent tracking
CREATE TABLE IF NOT EXISTS consent_records (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    session_id TEXT NOT NULL,
    consent_type TEXT NOT NULL,
    granted INTEGER DEFAULT 0,
    scope TEXT DEFAULT 'session'
);

CREATE INDEX IF NOT EXISTS idx_consent_session ON consent_records(session_id);

-- Record initial schema version
INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES ('0001', CURRENT_TIMESTAMP);
