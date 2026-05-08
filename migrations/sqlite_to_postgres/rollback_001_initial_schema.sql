-- rollback_001_initial_schema.sql
-- Rollback initial PostgreSQL schema migration

-- Drop tables in reverse order of dependencies
DROP TABLE IF EXISTS sensitive_signals;
DROP TABLE IF EXISTS continuity_markers;
DROP TABLE IF EXISTS events;
DROP TABLE IF EXISTS runtime_objects;
DROP TABLE IF EXISTS hermes_profiles;
DROP TABLE IF EXISTS gumi_instances;
DROP TABLE IF EXISTS subjects;

-- Verify tables dropped
SELECT 'All PostgreSQL tables dropped' AS status;
