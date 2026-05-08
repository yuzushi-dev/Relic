-- Rollback migration for shared_continuity_001_init
-- Removes all Shared Continuity Memory tables

BEGIN TRANSACTION;

-- Drop tables in reverse dependency order
DROP TABLE IF EXISTS continuity_scope;
DROP TABLE IF EXISTS continuity_edge;
DROP TABLE IF EXISTS continuity_event;
DROP TABLE IF EXISTS continuity_correction;
DROP TABLE IF EXISTS continuity_followup;
DROP TABLE IF EXISTS continuity_marker;

-- Remove version record
DROP TABLE IF EXISTS schema_version;

COMMIT;