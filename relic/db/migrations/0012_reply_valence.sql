ALTER TABLE checkin_exchanges ADD COLUMN reply_valence REAL;

INSERT OR REPLACE INTO schema_version (version, applied_at)
VALUES ('0012', CURRENT_TIMESTAMP);
