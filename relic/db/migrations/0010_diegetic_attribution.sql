-- Per-type cadence attribution for diegetic initiatives.

ALTER TABLE checkin_cadence_state ADD COLUMN diegetic_non_response_streak INTEGER;
ALTER TABLE checkin_cadence_state ADD COLUMN last_diegetic_delivered_at TEXT;

INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES ('0010', CURRENT_TIMESTAMP);
