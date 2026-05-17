# Export, Delete, and Forget Semantics

Relic implements three distinct data lifecycle operations:
**Export** (Art. 20 GDPR), **Delete** (Art. 17 GDPR), and **Forget** (right to erasure
with Gumi continuity purge).

---

## Export

Export produces a portable bundle of all subject data in a structured,
human-readable format conforming to `schemas/data-model/export_manifest.schema.json`.

### Safety Signals — excluded from export

Researcher-only safety signals (`sensitive_pattern_detected` events, CAC traces,
clinical risk scores) are **excluded** from subject-facing exports.
These records are subject-scoped but reserved for researcher review only.
Releasing them to the data subject without clinical context could cause harm.

The export manifest records `redaction_status: "redacted"` when any fields
have been excluded.

---

## Delete

Hard delete removes all persistent records for a subject_id. This operation:

- Is **subject-scoped** — it only removes data for the specified subject_id
  and does not affect any other subject.
- Emits an **audit** chronicle event (with `subject_id=None` and
  `subject_id_hash` in payload) before the delete sweep, so the operation
  is traceable without retaining the subject's PII.
- Covers: SQLite chronicle tables, JSONL journals, filesystem profile directory,
  and in-memory ContinuityService state.

The audit record survives the purge because the DELETE runs on
`WHERE subject_id = ?` and the audit event has `subject_id = NULL`.

---

## Forget

Forget removes data from **Gumi recall** without deleting the raw audit trail.
Specifically:

- Removes all ContinuityMarkers for the subject (prevents future recall
  of subject-stated information in Gumi context).
- Removes followups, corrections, and continuity scope entries
  for the subject.
- The subject-scoped Gumi recall is cleared so Gumi cannot reference
  past interactions. Historical chronicle events may be retained for
  research integrity under Art. 17(3)(d) exception, but the subject's
  active memory is purged.

### Subject isolation guarantee

Forget is **subject-scoped**: running `forget_subject("alice")` removes
only Alice's markers and scopes. Bob's data and any other subject's records
are untouched. Each forget operation targets exactly one subject_id.
