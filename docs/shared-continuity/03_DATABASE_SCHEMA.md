# Shared Continuity Memory — Database Schema

## MVP database

Use SQLite.

Database file:

```text
relic.db
```

Production migration target:

```text
PostgreSQL
```

## Tables

```text
continuity_markers
continuity_followups
continuity_corrections
continuity_events
continuity_marker_edges
continuity_scopes
```

## SQL schema

```sql
CREATE TABLE continuity_markers (
  marker_id TEXT PRIMARY KEY,
  subject_id TEXT NOT NULL,
  gumi_instance_id TEXT NOT NULL,
  hermes_profile_id TEXT NOT NULL,
  marker_type TEXT NOT NULL,
  subject_words TEXT NOT NULL,
  gumi_words TEXT,
  normalized_tags_json TEXT NOT NULL DEFAULT '[]',
  source TEXT NOT NULL,
  source_event_id TEXT,
  clinical_interpretation_allowed INTEGER NOT NULL DEFAULT 0,
  user_visible INTEGER NOT NULL DEFAULT 1,
  researcher_visible INTEGER NOT NULL DEFAULT 1,
  gumi_recall_allowed INTEGER NOT NULL DEFAULT 1,
  followup_allowed INTEGER NOT NULL DEFAULT 0,
  followup_style TEXT,
  status TEXT NOT NULL DEFAULT 'active',
  ttl_days INTEGER NOT NULL DEFAULT 14,
  recall_count INTEGER NOT NULL DEFAULT 0,
  max_recall_count INTEGER NOT NULL DEFAULT 2,
  created_at TEXT NOT NULL,
  updated_at TEXT
);
```

```sql
CREATE TABLE continuity_followups (
  followup_id TEXT PRIMARY KEY,
  marker_id TEXT NOT NULL,
  subject_id TEXT NOT NULL,
  gumi_instance_id TEXT NOT NULL,
  due_after TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  style TEXT NOT NULL DEFAULT 'gentle',
  attempt_count INTEGER NOT NULL DEFAULT 0,
  max_attempts INTEGER NOT NULL DEFAULT 1,
  if_ignored TEXT NOT NULL DEFAULT 'expire',
  created_at TEXT NOT NULL,
  updated_at TEXT,
  FOREIGN KEY(marker_id) REFERENCES continuity_markers(marker_id)
);
```

```sql
CREATE TABLE continuity_corrections (
  correction_id TEXT PRIMARY KEY,
  marker_id TEXT NOT NULL,
  subject_id TEXT NOT NULL,
  gumi_proposed_words TEXT,
  subject_correction TEXT NOT NULL,
  final_subject_words TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(marker_id) REFERENCES continuity_markers(marker_id)
);
```

```sql
CREATE TABLE continuity_events (
  event_id TEXT PRIMARY KEY,
  subject_id TEXT NOT NULL,
  gumi_instance_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  target_id TEXT NOT NULL,
  actor TEXT NOT NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL
);
```

```sql
CREATE TABLE continuity_marker_edges (
  edge_id TEXT PRIMARY KEY,
  subject_id TEXT NOT NULL,
  from_marker_id TEXT NOT NULL,
  to_marker_id TEXT NOT NULL,
  edge_type TEXT NOT NULL,
  created_at TEXT NOT NULL
);
```

```sql
CREATE TABLE continuity_scopes (
  scope_id TEXT PRIMARY KEY,
  subject_id TEXT NOT NULL,
  gumi_instance_id TEXT NOT NULL,
  scope_name TEXT NOT NULL,
  status TEXT NOT NULL,
  user_enabled INTEGER NOT NULL DEFAULT 0,
  researcher_enabled INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT
);
```

## Indexes

```sql
CREATE INDEX idx_markers_subject_status ON continuity_markers(subject_id, gumi_instance_id, status);
CREATE INDEX idx_markers_subject_created ON continuity_markers(subject_id, created_at);
CREATE INDEX idx_followups_due ON continuity_followups(subject_id, gumi_instance_id, status, due_after);
CREATE INDEX idx_events_subject_created ON continuity_events(subject_id, created_at);
CREATE INDEX idx_edges_from ON continuity_marker_edges(from_marker_id);
CREATE INDEX idx_edges_to ON continuity_marker_edges(to_marker_id);
```

## Vector search

Do not add vector search in MVP.

If added later:

```text
SQLite/Postgres remains source of truth.
Vector index is derived and rebuildable.
Vector search must not bypass visibility, TTL, pause, correction, or recall limits.
```
