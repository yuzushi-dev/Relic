# Hermes Integration

Gumi runs inside Hermes as a plugin. This page covers how to install, configure, **start**, and verify the integration.

## Quickstart: from bootstrap to first message

After `relic subject create` finishes, do this to actually deliver a message:

```bash
# 1. Provision a private Hermes profile for the subject (idempotent).
relic-profile hermes provision <subject_id>

# 2. Configure Telegram delivery (only if you skipped this during bootstrap).
relic-profile hermes configure-telegram <subject_id> \
  --bot-token-env GUMI_SUBJ01_BOT_TOKEN \
  --telegram-user-id 123456789

# 3. Add the subject to the delivery allowlist.
relic runtime allowlist add <subject_id> \
  --platform telegram \
  --target telegram:123456789

# 4. Export the bot token in the shell that will run Hermes.
export GUMI_SUBJ01_BOT_TOKEN="123456789:ABCdef..."

# 5. Start the Hermes gateway for this subject's profile.
#    The profile name was printed at the end of `relic subject create`.
#    By convention it is `gumi-<subject_id>`.
hermes gateway run --profile gumi-<subject_id>

# 6. Verify it is up.
hermes gateway list                # should show ✓ next to the profile
relic runtime status               # should report the plugin registered

# 7. From the subject's Telegram, send /start to the bot.
#    Then send Gumi's first contact:
relic-profile gumi intro send <subject_id> --deliver
```

If `/start` was never sent from the subject's Telegram, the bot cannot deliver anything. Telegram refuses to message a user who has not initiated.

To stop the gateway, hit `Ctrl-C` in the terminal running `hermes gateway run`. Run it again to resume.

To run it in the background and detach (Linux/macOS):

```bash
nohup hermes gateway run --profile gumi-<subject_id> > ~/.relic/gateway.log 2>&1 &
```

## Prerequisites

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

If you run Relic as a project-local Hermes plugin during development, Hermes
requires explicit trust for local plugins. Set
`HERMES_ENABLE_PROJECT_PLUGINS=true` only for repositories you control and
review. Production deployments should prefer the installed plugin path above.

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

## Quiet hours and frequency cap semantics

Set per-subject during `relic-profile hermes configure-telegram`. Defaults:

| Setting | Default | Format |
|---|---|---|
| `--quiet-hours` | `22:00-08:00` | `HH:MM-HH:MM`, **subject's local timezone** |
| `--maximum-contact-frequency` | `2/day` | `<N>/<window>` where window ∈ {`hour`, `day`, `week`} |
| `--delivery-windows` (API only) | `09:00-11:00`, `19:00-21:00` | List of `HH:MM-HH:MM`, subject's local timezone |
| `timezone` (API only) | `Europe/Rome` | IANA timezone, e.g. `America/New_York` |

### Rules

- **Quiet hours** are inclusive of the start, exclusive of the end. `22:00-08:00` covers `22:00:00` through `07:59:59` local time. Overnight windows are detected by `end < start`.
- **Timezone** is the **subject's** local timezone, set at bootstrap. Quiet hours are evaluated against the subject's wall clock, not the server's.
- **Frequency cap** counts every **outbound delivery attempt** that passed the gate, including dry-runs marked as sent. Failed/blocked attempts do not count.
- **Window reset:**
  - `N/hour`: rolling 60-minute window from the most recent send. Not a calendar hour.
  - `N/day`: calendar day in the subject's timezone, midnight-to-midnight.
  - `N/week`: ISO week (Mon–Sun) in the subject's timezone.
- **Delivery windows** intersect with allowed time. A send must satisfy *all* of: outside quiet hours, inside at least one delivery window, under frequency cap, on allowlist, subject not paused, consent valid.

### Edge cases

- **DST transitions:** the runtime uses zoneinfo arithmetic. The "lost hour" in spring is skipped; the "repeated hour" in autumn allows a single rolling-hour window across the boundary.
- **Boundary tick:** a cron tick that lands exactly at `08:00:00` is outside quiet hours and is evaluated normally.
- **Subject changes timezone:** update via re-running `configure-telegram`. Existing scheduled tasks are re-evaluated against the new timezone at the next tick.

### Inspect what the gate decided

```bash
chronicle decision --subject <subject_id> --kind delivery_gate --limit 5
```

Payload includes: `quiet_hours_active`, `frequency_cap_exhausted`, `pause_state`, `allowlist_match`, and the boolean `permit_send`.

## Cron-scheduled outreach

Proactive messages are managed via Hermes cron. To enable them for a subject, set `cron.enabled: true` in the plugin config. The schedule is defined in `relic/gumi_plugin/cron_schedule.py` and the specific tasks in `relic/gumi_plugin/cron_tasks.py`.

Cron tasks are subject-scoped. They cannot run outside the subject's consent and pause state.

## Diagnosing runtime issues

```bash
relic runtime status         # Hermes runtime status
relic runtime doctor         # Full runtime diagnostic
```

The `doctor` command checks Hermes connectivity, plugin registration, database access, Ollama model availability, and delivery channel configuration.
