-- 001_initial_schema.sql
-- Initial PostgreSQL schema migration from SQLite MVP

-- Create subjects table
CREATE TABLE IF NOT EXISTS subjects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_id TEXT NOT NULL UNIQUE,
    study_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create gumi_instances table
CREATE TABLE IF NOT EXISTS gumi_instances (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    gumi_instance_id TEXT NOT NULL UNIQUE,
    subject_id UUID NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create hermes_profiles table
CREATE TABLE IF NOT EXISTS hermes_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hermes_profile_id TEXT NOT NULL UNIQUE,
    gumi_instance_id UUID NOT NULL REFERENCES gumi_instances(id) ON DELETE CASCADE,
    profile_hash TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create runtime_objects table
CREATE TABLE IF NOT EXISTS runtime_objects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    object_id TEXT NOT NULL UNIQUE,
    subject_id TEXT NOT NULL,
    gumi_instance_id TEXT NOT NULL,
    hermes_profile_id TEXT NOT NULL,
    object_type TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create events table
CREATE TABLE IF NOT EXISTS events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id TEXT NOT NULL UNIQUE,
    subject_id TEXT NOT NULL,
    gumi_instance_id TEXT NOT NULL,
    hermes_profile_id TEXT NOT NULL,
    event_class TEXT,
    ontological_class TEXT,
    timestamp TIMESTAMPTZ,
    source_refs JSONB,
    policy_snapshot_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create continuity_markers table
CREATE TABLE IF NOT EXISTS continuity_markers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    marker_id TEXT NOT NULL UNIQUE,
    subject_id TEXT NOT NULL,
    gumi_instance_id TEXT NOT NULL,
    hermes_profile_id TEXT NOT NULL,
    marker_type TEXT,
    content_hash TEXT,
    confirmed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create sensitive_signals table
CREATE TABLE IF NOT EXISTS sensitive_signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id TEXT NOT NULL UNIQUE,
    subject_id TEXT NOT NULL,
    gumi_instance_id TEXT NOT NULL,
    hermes_profile_id TEXT NOT NULL,
    signal_type TEXT,
    detected_at TIMESTAMPTZ,
    researcher_visible BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_gumi_instances_subject_id ON gumi_instances(subject_id);
CREATE INDEX IF NOT EXISTS idx_hermes_profiles_gumi_instance_id ON hermes_profiles(gumi_instance_id);
CREATE INDEX IF NOT EXISTS idx_runtime_objects_subject_id ON runtime_objects(subject_id);
CREATE INDEX IF NOT EXISTS idx_events_subject_id ON events(subject_id);
CREATE INDEX IF NOT EXISTS idx_continuity_markers_subject_id ON continuity_markers(subject_id);
CREATE INDEX IF NOT EXISTS idx_sensitive_signals_subject_id ON sensitive_signals(subject_id);

-- Verify table creation
SELECT 'Tables created successfully' AS status;
