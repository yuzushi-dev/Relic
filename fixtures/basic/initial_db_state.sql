-- Basic fixture for relic database
-- Used for testing and development

-- Initialize schema version if not already set
INSERT OR IGNORE INTO schema_version (version, applied_at) VALUES ('0001', CURRENT_TIMESTAMP);

-- Sample prompt records (privacy-safe: hashes only)
INSERT INTO prompt_records (id, session_id, role, content_hash, content_length, is_redacted)
VALUES 
    ('550e8400-e29b-41d4-a716-446655440001', '550e8400-e29b-41d4-a716-446655440000', 'user', 
     'a1b2c3d4e5f6789012345678901234567890', 42, 0),
    ('550e8400-e29b-41d4-a716-446655440002', '550e8400-e29b-41d4-a716-446655440000', 'assistant',
     'b2c3d4e5f67890123456789012345678901', 128, 0);

-- Sample consent record
INSERT INTO consent_records (id, session_id, consent_type, granted, scope)
VALUES 
    ('660e8400-e29b-41d4-a716-446655440001', '550e8400-e29b-41d4-a716-446655440000', 'memory_persistence', 1, 'session');
