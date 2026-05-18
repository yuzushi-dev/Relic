# Hermes Integration

Gumi runs inside Hermes as a plugin. This page covers how to install and configure the integration.

## Prerequisites

- Hermes installed and configured (see [Installation](installation.md))
- At least one subject created with `relic subject create`
- Delivery allowlist configured for the subject

## Plugin files

The Relic/Gumi plugin installs to `~/.hermes/plugins/gumi-relational/`:

```
gumi-relational/
  plugin.yaml
  __init__.py
  hooks.py        (pre_llm_call, post_llm_call)
  tools.py        (researcher-facing tools: /relic why, /relic pause)
  admission.py    (roleplay and continuity admission)
  continuity.py   (continuity marker handling)
  storage.py      (per-session state)
```

The plugin is registered with Hermes when you run `relic subject create` or `relic subject reprovision`. You can verify it is active:

```bash
hermes plugin list | grep gumi-relational
```

## Plugin configuration

A minimal plugin configuration is provided in `configs/hermes/gumi-plugin.example.yaml`. Copy it to your Hermes plugins directory and edit for your subject:

```yaml
plugin: gumi-relational
subject_id: your_subject_id
gumi_instance_id: auto
relic_db_path: ~/.relic/relic.db

memory:
  provider: hindsight          # Options: hindsight, byterover, holographic, honcho
  local_mode: true             # Use local Ollama for embedding

cron:
  enabled: false               # Set to true to allow proactive outreach
  wrap_response: false

safety:
  escalation_notify: true
  researcher_email: you@example.com
```

## Hermes hooks

Two hooks run per turn:

**`pre_llm_call`** — runs before the LLM call. Classifies the task, retrieves memory and continuity candidates, runs them through the Relic gates, assembles the PromptContextPack, and injects it as ephemeral context.

**`post_llm_call`** — runs after the LLM call. Evaluates the output against the critic rubric, writes continuity traces and exposure events, and checks output safety.

Hook failures produce no memory injection (not a partial injection). If the plugin fails, Gumi continues with only her SOUL.md and Hermes's own context — personalization is suppressed, not corrupted.

## Researcher tools

The plugin exposes two tools the researcher can call manually:

```
/relic why      Show the CAC trace for the last turn
/relic pause    Pause all runtime guidance for this subject
```

These are defined in `relic/gumi_plugin/tools.py` and are not exposed to subjects.

## Delivery channels

To enable live delivery to a subject, add their contact to the allowlist:

```bash
relic runtime allowlist add <subject_id> \
  --platform telegram \
  --target telegram:123456789 \
  --expires 2026-12-31T00:00:00Z
```

Supported platforms: `telegram`, `whatsapp`. The `--expires` flag is optional; allowlist entries without an expiry remain active until explicitly removed.

To list active allowlist entries:

```bash
relic runtime allowlist list <subject_id>
```

To remove an entry:

```bash
relic runtime allowlist remove <subject_id> --platform telegram --target telegram:123456789
```

## SOUL.md

Gumi's stable identity lives in `$HERMES_HOME/SOUL.md`. It is generated during bootstrap and reviewed in the bootstrap TUI. After it is generated, treat it as a configuration file: edit it by going back through `relic subject create` rather than editing it manually, so changes are tracked.

SOUL.md is never modified by the plugin at runtime. The plugin adds ephemeral per-turn context on top of it.

## Cron-scheduled outreach

Proactive messages are managed via Hermes cron. To enable them for a subject, set `cron.enabled: true` in the plugin config. The schedule is defined in `relic/gumi_plugin/cron_schedule.py` and the specific tasks in `relic/gumi_plugin/cron_tasks.py`.

Cron tasks are subject-scoped. They cannot run outside the subject's consent and pause state.

## Diagnosing runtime issues

```bash
relic runtime status         # Hermes runtime status
relic runtime doctor         # Full runtime diagnostic
```

The `doctor` command checks Hermes connectivity, plugin registration, database access, Ollama model availability, and delivery channel configuration.
