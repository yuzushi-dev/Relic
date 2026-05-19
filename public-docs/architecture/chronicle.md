# Chronicle: the Audit Ledger

Chronicle is Relic's append-only event ledger. Every meaningful runtime decision — a CAC ruling, a delivery gate, a correction propagation, an artifact compile, a consent change — is written as an event with structured metadata. The ledger is what makes the system auditable, reproducible, and contestable.

The CLI surface is documented separately in [`chronicle` CLI reference](../reference/chronicle-cli.md). This page covers **what it is**, **when to use it**, and **how to read it**.

## When to use the workbench vs. chronicle

| Question | Use |
|---|---|
| "What does the system currently believe about this subject?" | Workbench (`relic ui`) |
| "Why did Gumi not reply at 9 a.m.?" | `chronicle decision --kind delivery_gate` |
| "Which artifact version was active when this turn happened?" | `chronicle provenance --artifact <id>` |
| "Has anyone read this subject's data this week?" | `chronicle query --type access` |
| "What changed between yesterday and today?" | `chronicle timeline --since 24h` |
| "Export everything the auditor will ask for" | `chronicle export --subject <id>` |

The workbench answers "what is true now." Chronicle answers "what happened, when, and why." Both read from the same `relic.db`; chronicle is the time-ordered, structured-event view.

## Why an append-only ledger

Three properties matter:

1. **Reproducibility.** A replication bundle is only meaningful if every decision is reconstructable. Chronicle stores the inputs, the policy snapshot, and the outcome of each decision.
2. **Contestability.** A correction or a subject complaint should be answerable with evidence, not inferred from the current state.
3. **Retention and deletion governance.** Each event carries a retention policy and a visibility level. The retention reaper acts on those tags, not on side-channel rules.

Events are written via `relic/chronicle/emitter.py` in a dual-write pattern: SQLite for query, JSONL for offline forensics. The two are kept consistent by `chronicle verify`.

## Event model

Every chronicle event has these fields (see `relic/chronicle/schema.py`):

| Field | Meaning |
|---|---|
| `event_id` | UUID, primary key |
| `event_type` | Specific event, e.g. `cac_decision`, `correction_applied`, `consent_revoked` |
| `event_category` | Coarse bucket — `message`, `decision`, `safety`, `consent`, `privacy`, … |
| `subject_id` | Subject scope (may be null for admin events) |
| `session_id` | Session scope |
| `trace_id` | Joins related events across modules within one turn |
| `source_module` | Which Relic module emitted the event |
| `timestamp` | ISO 8601, UTC |
| `payload` | Structured event-specific data |
| `retention_policy` | `ephemeral`, `short_30d`, `standard_365d`, `extended_research`, `legal_hold` |
| `visibility_level` | `researcher`, `admin`, `subject_export` |
| `reasoning_capture` | `none`, `metrics_only`, `redacted_summary`, `raw_researcher_only` |
| `privacy_level` | Source-of-truth from `relic.persistence` |

Decisions also store a `decision_kind` and a `validation_status` (`pending`, `validated`, `superseded`, `disputed`, `failed`). State snapshots include a `snapshot_type` and a `scope`.

## Event categories

The taxonomy in `relic/chronicle/enums.py`:

- `message` — turn-level conversational data.
- `model` — LLM call metadata.
- `tool` — tool invocations.
- `memory` — memory store/retrieve.
- `profile` — facet/inference/profile updates.
- `decision` — CAC rulings, delivery gates, admission decisions, cron decisions.
- `artifact` — compiler runs, artifact lifecycle transitions.
- `safety` — safety signal emissions (researcher-only).
- `privacy` — redaction scans and gate decisions.
- `consent` — consent grants and revocations.
- `admin` — operator actions.
- `eval` — evaluation runs.
- `background` — cron and maintenance.
- `error` — failures.
- `state_snapshot` — periodic state snapshots.
- `provenance` — PROV-O edges across artifacts and decisions.

Use `--category` on `chronicle query` to filter by bucket.

## Common recipes

**Why did Gumi not message at 9 a.m. today?**

```bash
chronicle decision \
  --subject subj_demo_01 \
  --kind delivery_gate \
  --limit 10
```

Look at the `payload`: it includes the allowlist state, pause state, quiet-hours match, frequency cap, and the boolean outcome.

**What did the CAC actually inject in the last turn?**

```bash
chronicle decision \
  --subject subj_demo_01 \
  --kind cac_decision \
  --limit 1
```

Or from inside the Hermes session: `/relic why`.

**Trace an artifact back to its evidence.**

```bash
chronicle provenance --artifact <artifact_id> --direction ancestors --depth 5
```

Returns the PROV-O graph of inputs that produced the artifact, all the way back to the originating evidence events.

**Verify a deletion was actually executed.**

```bash
chronicle query \
  --subject <subject_id> \
  --category admin \
  --type subject_forgotten \
  --limit 1
```

`relic subject forget` emits this event with the anonymised (hashed) subject ID **before** erasure.

**Compute weekly stats for a subject.**

```bash
chronicle stats --subject subj_demo_01 --since 2026-05-11T00:00:00Z
```

**Inspect a single trace end-to-end.**

```bash
chronicle timeline --trace <trace_id> --group-by time
```

A `trace_id` joins every event from a single turn: model call → tool calls → memory writes → decisions → artifact reads.

## Reading vs writing

Chronicle is **read-only for researchers** at the CLI. Writes happen only when:

- A Relic module emits an event during normal operation.
- `chronicle delete` removes events for a subject (audited).
- `chronicle reaper` enforces retention policies (audited).
- `chronicle verify --repair` reconciles SQLite ↔ JSONL gaps (audited).

Every read is itself audited (event category `admin`, type `access`) unless `--no-audit` is passed — and that flag is recorded too.

## Retention and visibility

Each event row carries a `retention_policy` and a `visibility_level`. The retention reaper (`chronicle reaper`) walks the ledger and deletes only events whose policy permits deletion at the current time. `legal_hold` is never auto-deleted.

`visibility_level` controls inclusion in subject exports: only events tagged `subject_export` appear in a GDPR-style subject bundle. Safety events default to `researcher` and stay out of subject exports by design.

### Retention policies

Defined in `relic/chronicle/enums.py`. The reaper's behaviour is in `relic/chronicle/retention.py`.

| Policy | Lifetime | Reaper behaviour |
|---|---|---|
| `ephemeral` | < 1 hour | Auto-delete on every reaper run |
| `short_30d` | 30 days | Auto-delete after 30 days |
| `standard_365d` (default) | 365 days | Auto-delete after 1 year |
| `extended_research` | 3 years, researcher-only | Auto-delete after 3 years; not in subject exports |
| `legal_hold` | indefinite | Never auto-delete; requires explicit `chronicle delete` |

The **default for every emitter** is `standard_365d` unless the call site overrides it (see `emitter.py:209`, `emitter.py:437`, `snapshots.py:144`). Override at write time per event type; do not retroactively change retention for already-emitted events.

### Default mapping by category (current behaviour)

There is no fixed `category → policy` map in code; every emit site picks its own. As shipped, almost everything uses `standard_365d`. Two notable exceptions you will see in practice:

- **Access audit events** (`chronicle access_log`): `standard_365d` — they are how you answer "who read this and when."
- **Long-term provenance edges**: emitted with `standard_365d` but typically the artefacts they describe live longer; consider promoting to `extended_research` if you need to defend reproducibility past one year.

If you need a different policy for a study (e.g. all safety events to `extended_research` for IRB compliance), wrap the emitter call sites with a project-level config rather than editing per-event defaults.

## Provenance (PROV-O)

Provenance edges follow the W3C [PROV-O](https://www.w3.org/TR/prov-o/) vocabulary. Relations include `used`, `wasGeneratedBy`, `wasDerivedFrom`, `wasInformedBy`, `wasAssociatedWith`, `actedOnBehalfOf`, `hadMember`, `wasTriggeredBy`, `wasControlledBy`. This makes chronicle interoperable with standard provenance tooling.

## When chronicle is the wrong tool

- For **what the system currently believes**, use the workbench. Reconstructing current state from the event stream is possible but wasteful — the workbench reads compiled state directly.
- For **subject-facing exports**, prefer `relic-profile export` for the profile bundle and `chronicle export --subject ID` for the event ledger; the two are designed to be paired.
- For **debugging plugin failures**, the plain Hermes log is usually faster than chronicle. Chronicle records *decisions*, not stack traces.

## Where to go next

- [`chronicle` CLI reference](../reference/chronicle-cli.md) — full command surface.
- [Daily Operations](../guides/daily-operations.md) — chronicle one-liners for the morning routine.
- [Artifact Lifecycle](artifact-lifecycle.md) — how artifacts and their provenance are produced.
- [Privacy Stages](privacy-stages.md) — how `privacy_level` interacts with event admission.
