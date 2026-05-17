-- Chronicle provenance edges table
-- Version: 0006
-- Schema: chronicle-provenance/v1
-- Reference: docs/chronicle/agentic-development-plan.md §6.4
-- Relation types: PROV-O (used, wasGeneratedBy, wasDerivedFrom, wasInformedBy, hadMember, actedOnBehalfOf)

CREATE TABLE IF NOT EXISTS chronicle_provenance_edges (
    edge_id                TEXT PRIMARY KEY,
    trace_id               TEXT NOT NULL,
    artifact_id            TEXT NOT NULL,
    from_node_type         TEXT NOT NULL,
    from_node_id           TEXT NOT NULL,
    relation               TEXT NOT NULL,
    contribution_role      TEXT,
    weight                 REAL DEFAULT 1.0,
    timestamp              TEXT NOT NULL,
    schema_version         TEXT NOT NULL DEFAULT 'chronicle-provenance/v1',
    created_at             TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_chronicle_prov_artifact     ON chronicle_provenance_edges(artifact_id);
CREATE INDEX IF NOT EXISTS idx_chronicle_prov_trace        ON chronicle_provenance_edges(trace_id);
CREATE INDEX IF NOT EXISTS idx_chronicle_prov_from_node    ON chronicle_provenance_edges(from_node_type, from_node_id);
CREATE INDEX IF NOT EXISTS idx_chronicle_prov_relation     ON chronicle_provenance_edges(relation);
CREATE INDEX IF NOT EXISTS idx_chronicle_prov_timestamp    ON chronicle_provenance_edges(timestamp);

INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES ('0006', CURRENT_TIMESTAMP);
