# Shared Continuity Memory — Marker Lifecycle

## Marker states

```text
draft
active
corrected
rejected
expired
forgotten
paused
```

## Creation rule

A marker may be created only if:

```text
the subject asked Gumi to remember
or the subject confirmed Gumi's proposed wording
or the marker is a direct continuation of an already confirmed thread
```

## Creation example

User:

```text
Today was too fast. I slept three hours and I am still running.
```

Gumi:

```text
Do you want me to keep it as "too fast, low sleep" so tomorrow I do not start from zero?
```

If the user confirms, the marker is created.

## Correction rule

If the subject corrects Gumi, the correction becomes authoritative.

Example:

```text
Gumi proposed: accelerated
Subject correction: not accelerated, just happy
Final subject words: happy, high energy, low sleep
```

Future recall must use the correction.

## Follow-up rule

Follow-up is allowed only when:

```text
followup_allowed = true
followup.status = pending
attempt_count < max_attempts
scope is not paused
quiet hours do not block
burden signal does not block
```

Default:

```text
max_attempts = 1
if_ignored = expire
```

## Expiration rule

Sensitive continuity markers should expire unless pinned by the subject.

Default TTL:

```text
14 days
```

Suggested TTL:

```text
day_marker: 14 days
open_thread: 7 days
sleep_marker: 7 days
user_named_warning_sign: until subject edits/removes
```

## Recall ranking

Prefer:

```text
subject-confirmed markers
due follow-ups
recent markers
corrected markers with final subject words
markers linked to current conversation
```

Avoid:

```text
ignored follow-ups
expired markers
rejected markers
markers from paused scopes
markers already recalled too often
markers with burden signals
```
