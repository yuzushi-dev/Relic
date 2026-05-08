-- 002_backfill_cascade.sql
-- Backfill data from SQLite into PostgreSQL with FK cascade preservation

-- Step 1: Backfill subjects
INSERT INTO subjects (id, subject_id, study_id, created_at)
SELECT
    gen_random_uuid(),
    id,
    study_id,
    COALESCE(created_at, NOW())::TIMESTAMPTZ
FROM sqlite_subjects;

-- Step 2: Backfill gumi_instances with FK to subjects
INSERT INTO gumi_instances (id, gumi_instance_id, subject_id, created_at)
SELECT
    gen_random_uuid(),
    gi.id,
    s.id,
    COALESCE(gi.created_at, NOW())::TIMESTAMPTZ
FROM sqlite_gumi_instances gi
JOIN subjects s ON s.subject_id = gi.subject_id;

-- Step 3: Backfill hermes_profiles with FK to gumi_instances
INSERT INTO hermes_profiles (id, hermes_profile_id, gumi_instance_id, profile_hash, created_at)
SELECT
    gen_random_uuid(),
    hp.id,
    gi.id,
    hp.profile_hash,
    COALESCE(hp.created_at, NOW())::TIMESTAMPTZ
FROM sqlite_hermes_profiles hp
JOIN gumi_instances gi ON gi.gumi_instance_id = hp.gumi_instance_id;

-- Step 4: Backfill runtime_objects
INSERT INTO runtime_objects (id, object_id, subject_id, gumi_instance_id, hermes_profile_id, object_type, created_at)
SELECT
    gen_random_uuid(),
    ro.id,
    ro.subject_id,
    ro.gumi_instance_id,
    ro.hermes_profile_id,
    ro.object_type,
    COALESCE(ro.created_at, NOW())::TIMESTAMPTZ
FROM sqlite_runtime_objects ro;

-- Step 5: Backfill events
INSERT INTO events (id, event_id, subject_id, gumi_instance_id, hermes_profile_id, event_class, ontological_class, timestamp, source_refs, policy_snapshot_id, created_at)
SELECT
    gen_random_uuid(),
    e.id,
    e.subject_id,
    e.gumi_instance_id,
    e.hermes_profile_id,
    e.event_class,
    e.ontological_class,
    COALESCE(e.timestamp, NOW())::TIMESTAMPTZ,
    e.source_refs::JSONB,
    e.policy_snapshot_id,
    COALESCE(e.created_at, NOW())::TIMESTAMPTZ
FROM sqlite_events e;

-- Step 6: Backfill continuity_markers
INSERT INTO continuity_markers (id, marker_id, subject_id, gumi_instance_id, hermes_profile_id, marker_type, content_hash, confirmed, created_at)
SELECT
    gen_random_uuid(),
    cm.id,
    cm.subject_id,
    cm.gumi_instance_id,
    cm.hermes_profile_id,
    cm.marker_type,
    cm.content_hash,
    COALESCE(cm.confirmed, FALSE),
    COALESCE(cm.created_at, NOW())::TIMESTAMPTZ
FROM sqlite_continuity_markers cm;

-- Step 7: Backfill sensitive_signals
INSERT INTO sensitive_signals (id, signal_id, subject_id, gumi_instance_id, hermes_profile_id, signal_type, detected_at, researcher_visible, created_at)
SELECT
    gen_random_uuid(),
    ss.id,
    ss.subject_id,
    ss.gumi_instance_id,
    ss.hermes_profile_id,
    ss.signal_type,
    COALESCE(ss.detected_at, NOW())::TIMESTAMPTZ,
    COALESCE(ss.researcher_visible, TRUE),
    COALESCE(ss.created_at, NOW())::TIMESTAMPTZ
FROM sqlite_sensitive_signals ss;

-- Verify row counts
SELECT
    'subjects' AS table_name,
    COUNT(*) AS row_count
FROM subjects
UNION ALL
SELECT 'gumi_instances', COUNT(*) FROM gumi_instances
UNION ALL
SELECT 'hermes_profiles', COUNT(*) FROM hermes_profiles
UNION ALL
SELECT 'runtime_objects', COUNT(*) FROM runtime_objects
UNION ALL
SELECT 'events', COUNT(*) FROM events
UNION ALL
SELECT 'continuity_markers', COUNT(*) FROM continuity_markers
UNION ALL
SELECT 'sensitive_signals', COUNT(*) FROM sensitive_signals;
