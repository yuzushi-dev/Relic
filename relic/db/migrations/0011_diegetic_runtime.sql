-- Per-subject runtime knobs for diegetic sharing posture and backoff.

ALTER TABLE checkin_cadence_state ADD COLUMN diegetic_intensity REAL;
ALTER TABLE checkin_cadence_state ADD COLUMN diegetic_frequency REAL;

INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES ('0011', CURRENT_TIMESTAMP);
