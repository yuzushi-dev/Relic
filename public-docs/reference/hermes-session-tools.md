# Hermes Session Tools (`/relic ...`)

Researcher-facing commands you can type **inside an active Hermes session**. These are not CLI commands and are not exposed to the subject. They are ephemeral: nothing is added to Gumi's memory, and every invocation is audit-logged.

Source: `relic/hermes_plugin/commands.py`.

## Properties

- **Researcher-only.** Subjects never see these prompts and never see the responses.
- **Ephemeral.** No persistent memory modification.
- **Audited.** Every invocation writes a chronicle event.
- **Fail-safe.** Errors fail closed: the command reports a failure, the session continues normally.

## Commands

### `/relic why`

Show the CAC trace for the most recent turn in this session.

```
/relic why
```

Output (shape):

| Field | Meaning |
|---|---|
| `trace_id` | UUID of the trace; usable with `chronicle decision --trace`. |
| `memory_id` | Candidate the trace concerns. |
| `decision` | One of `none`, `compact`, `expanded`, `local_only`, `deferred`, `quarantine`, `blocked`. |
| `severity` | `none`, `s2`, `s1`, `s0`. |
| `skip_reason` | Why a non-admitted candidate was skipped. |
| `timestamp` | When the decision was made. |
| `metadata` | Factors and rule-evaluation context. |

Use it when you want a quick read in-session. For systematic queries, prefer `chronicle decision --kind cac_decision`.

### `/relic pause`

Pause runtime guidance for this session. CAC suppresses personalization and the cron stops issuing proactive tasks for the session's subject.

```
/relic pause
```

Returns:

| Field | Meaning |
|---|---|
| `success` | Whether the pause was applied. |
| `paused` | Current pause state. |
| `message` | Human-readable note. |
| `session_id` | The session ID for which pause was set. |

Pause is **session-scoped**. To pause a subject globally, run it inside every active session for that subject or use the workbench pause panel.

### `/relic resume`

Lift a pause set by `/relic pause` in the same session.

```
/relic resume
```

Returns the same shape as `/relic pause` with `paused: false` on success.

Restarting the gateway also lifts session-level pauses since session state is in-process.

### `/relic status`

Snapshot of the current session's runtime state.

```
/relic status
```

Output:

| Field | Meaning |
|---|---|
| `plugin_loaded` | Is the Relic plugin active in this Hermes session? |
| `guidance_paused` | Is runtime guidance currently paused? |
| `last_trace_available` | Is there a CAC trace `/relic why` can show? |
| `policy_version` | The policy snapshot version active for this session. |
| `session_id` | The session ID. |

Use it as the in-session counterpart to `relic runtime doctor`.

## What these tools cannot do

- **They cannot write to the subject profile.** No corrections, no facet edits. Use the workbench.
- **They cannot change SOUL.md.** SOUL.md is bootstrap-only.
- **They cannot expose raw safety signal evidence.** Use `chronicle query --category safety --reasoning-capture raw_researcher_only` from the CLI.
- **They cannot deliver messages.** Delivery is via the gateway, not the tools surface.

## Auditing

Every `/relic ...` invocation produces a chronicle event:

```bash
chronicle query --subject <subject_id> --type relic_command --limit 20
```

The payload records the command, the session, the outcome, and the researcher identity if one is asserted.

## Gumi-side tools

A separate set of tools is exposed **to Gumi** (not to the researcher) by the gumi plugin. Currently:

| Tool | Description | Mutating? |
|---|---|---|
| `gumi.recall` | Read continuity diary entry | No |
| `gumi.snapshot` | Return current world-state snapshot | No |
| `gumi.write_diary` | Append diary entry | Yes (requires admission policy + permission) |

Source: `relic/gumi_plugin/tools.py`. These are not invoked by the researcher; they are part of Gumi's own scaffold and surface as model-callable tools when admission allows.
