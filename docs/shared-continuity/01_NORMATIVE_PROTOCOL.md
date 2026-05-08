# Shared Continuity Memory - Normative Protocol

## Status

Normative.

## Definition

Shared Continuity Memory is a subject-scoped relational memory layer that stores user-confirmed continuity markers, corrections, follow-up permissions, recall limits, and audit events so that Gumi can remember like a relational partner rather than retrieve like a search engine.

## Design principle

```text
Relational continuity first.
Structured tracking second.
```

The conversation must not bend around the data. Data is created only when it preserves continuity that the subject chose to share.

## What this is

```text
relational continuity
user-confirmed markers
subject words
gentle follow-up
correctable memory
auditable memory
non-diagnostic memory
```

## What this is not

```text
mood tracker
symptom tracker
clinical monitor
pathology detector
diagnostic system
general vector memory
Hindsight replacement
Hermes native memory replacement
```

## User-facing language

Allowed:

```text
I remember.
I will keep that in mind.
I will keep the thread.
Do you want me to remember it that way?
Yesterday you called it “too fast”.
Do you want me to let this go?
```

Forbidden:

```text
I logged a tracking entry.
I detected a pattern.
The system noticed.
This is a symptom.
This suggests hypomania.
This looks like depression.
I classified your mood.
```

## Clinical boundary

Forbidden runtime terms:

```text
bipolar
mania
hypomania
depression
episode
symptom
diagnosis
relapse
pathology
clinical risk
```

Exception:

```text
If the subject explicitly used a term, it may exist only in raw source text or subject_words, not as system inference, normalized tag, Gumi label, or policy output.
```

## Required lifecycle

```text
subject shares something
↓
Gumi responds relationally
↓
Gumi proposes a continuity marker, if appropriate
↓
subject confirms or corrects
↓
Relic stores marker
↓
Relic may create follow-up
↓
Hermes recalls only due, allowed, non-expired markers
↓
Gumi follows up gently or says nothing
```

## Recall rule

Gumi may recall a marker only if all are true:

```text
marker.status = active
marker.gumi_recall_allowed = true
marker.ttl not expired
marker.recall_count < marker.max_recall_count
subject scope matches current Hermes profile
no pause is active for the marker scope
no recent burden signal blocks recall
the marker was subject-confirmed or subject-authored
```

## Hindsight rule

Safe flow:

```text
Hindsight candidate
↓
Relic evaluates consent/visibility
↓
Gumi asks confirmation if appropriate
↓
only confirmed marker enters Shared Continuity Memory
```

Forbidden flow:

```text
Hindsight recall
↓
Gumi directly follows up on sensitive content
```
