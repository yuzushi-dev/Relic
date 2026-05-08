-- rollback_002_backfill_cascade.sql
-- Rollback backfill data migration

-- Note: This rollback assumes data was exported to intermediate JSON before backfill
-- If using a proper backup, restore from backup before running rollback_001_initial_schema.sql

-- Delete data in reverse order of dependencies
DELETE FROM sensitive_signals;
DELETE FROM continuity_markers;
DELETE FROM events;
DELETE FROM runtime_objects;
DELETE FROM hermes_profiles;
DELETE FROM gumi_instances;
DELETE FROM subjects;

-- Verify all data deleted
SELECT
    'sensitive_signals' AS table_name,
    COUNT(*) AS remaining_rows
FROM sensitive_signals
UNION ALL
SELECT 'continuity_markers', COUNT(*) FROM continuity_markers
UNION ALL
SELECT 'events', COUNT(*) FROM events
UNION ALL
SELECT 'runtime_objects', COUNT(*) FROM runtime_objects
UNION ALL
SELECT 'hermes_profiles', COUNT(*) FROM hermes_profiles
UNION ALL
SELECT 'gumi_instances', COUNT(*) FROM gumi_instances
UNION ALL
SELECT 'subjects', COUNT(*) FROM subjects;

-- Note: After this rollback, run rollback_001_initial_schema.sql to drop the schema
SELECT 'Backfill rollback complete. Run rollback_001_initial_schema.sql next.' AS next_step;
