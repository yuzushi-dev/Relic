# Researcher Workbench - Shared Continuity Panel

## Panel name

```text
Shared Continuity
```

Do not call it:

```text
Mood Tracking
Symptoms
Diagnostics
Clinical Signals
```

## Marker row fields

```text
subject_words
gumi_words
normalized_tags
source
status
followup_status
recall_count / max_recall_count
ttl
last_recalled_at
clinical_interpretation_allowed: false
correction_status
created_at
```

## Detail view

```text
marker_id
subject_id
gumi_instance_id
hermes_profile_id
marker_type
subject_words
gumi_words
normalized tags
source event
follow-up policy
corrections
edges to other markers
audit events
delete/forget action
pause scope action
```

## Researcher actions

Allowed:

```text
view marker
view correction
view audit events
expire marker
pause scope
resume scope
mark as research-visible only
delete marker if protocol allows
```

Forbidden:

```text
convert marker into diagnosis
send hidden clinical label to Gumi
force recall of rejected marker
bypass subject pause
```

## Required notice

```text
Shared Continuity markers are relational memory objects, not clinical findings. They preserve the subject's own words and confirmed threads.
```
