# Configuration Reference

All configuration is driven by environment variables. The installer writes
them to `.env` at the repo root. Load it however you prefer:

```bash
source .env          # bash
set -a && source .env && set +a    # export all
```

OpenClaw crons receive their env vars directly via `--env` flags at
registration time (set by the installer). You do not need to load `.env`
for cron jobs.

---

## Subject

```env
RELIC_SUBJECT_ID=alice
```
Slug used as a key in logs, database records, and file names. No spaces.
Must match the ID portion of the `from` field in captured messages
(`telegram:<RELIC_SUBJECT_ID>`).

```env
RELIC_SUBJECT_NAME=Alice
```
Display name used in portrait headers and console output.

```env
RELIC_TELEGRAM_ID=123456789
```
Numeric Telegram sender ID of the subject. Used by the check-in delivery
system to route outbound questions to the correct Telegram user. Obtain it
from your Telegram client or by inspecting a raw message event in OpenClaw.
Optional - leave blank if you are not using Telegram check-ins.

Note: message filtering in the capture hook is controlled by
`RELIC_SUBJECT_ID`, not this field. The capture hook matches the
`from` field of incoming events against `RELIC_SUBJECT_ID`.

---

## Paths

```env
RELIC_DATA_DIR=~/.relic/alice
```
Root directory for all runtime state. Created by the installer.

Expected contents after first run:

```
~/.relic/alice/
├── inbox.jsonl              ← inbound messages captured by hook
├── relic.db            ← SQLite: observations, facets, hypotheses
├── PORTRAIT.md              ← human-readable behavioral portrait (injected into agents)
├── subject_profile.json     ← machine-readable trait snapshot
├── pending-checkin.json     ← signal file: check-in reply window active
└── delivery.jsonl           ← outbound delivery log
```

```env
OPENCLAW_HOME=~/.openclaw
```
Root directory of your OpenClaw installation. Used to resolve the default
hooks directory and OpenClaw runtime paths.

```env
OPENCLAW_BIN=openclaw
```
Path or name of the OpenClaw CLI binary. Override if it is not in `PATH`.

---

## Check-in schedule

These variables are informational - they document the schedule the installer
burned into the cron registration. To change the schedule, re-register the
cron with a new `--schedule` flag.

```env
RELIC_CHECKIN_HOUR_START=9
RELIC_CHECKIN_HOUR_END=22
RELIC_CHECKIN_INTERVAL_MIN=30
# Resulting cron: */30 9-22 * * *
```

```env
RELIC_FOLLOWUP_CRON=relic:checkin-followup
```
OpenClaw cron name that the capture hook invokes when a check-in reply is
detected. Must match the cron name registered with OpenClaw. Default is
`relic:checkin-followup`.

---

## Cron identifiers (reference)

**Core pipeline**

| Cron name | Schedule | What it runs |
|---|---|---|
| `relic:extract` | `0 */2 * * *` | LLM extraction pass on new inbox messages |
| `relic:checkin` | `*/30 9-22 * * *` | Gap-score probe → sends question via Telegram |
| `relic:passive-scan` | `0 */6 * * *` | Scans relational-agent session transcripts |
| `relic:reply-extract` | `0 */6 * * *` | LLM extraction on captured check-in replies |
| `relic:synthesize` | `0 3 * * *` | Consolidates observations → trait scores + hypotheses |
| `relic:profile-sync` | `30 3 * * *` | Syncs model to `subject_profile.json` and `PORTRAIT.md` |
| `relic:checkin-followup` | on-demand | Acknowledges a check-in reply; triggered by capture hook |

**Daily enrichment**

| Cron name | Schedule | What it runs |
|---|---|---|
| `relic:entity-extract` | `0 4 * * *` | Entity graph extraction (people, places, topics) |
| `relic:decisions` | `15 4 * * *` | Decision extraction and coherence scoring |
| `relic:healthcheck` | `0 4 * * *` | Database integrity and cron freshness check |
| `relic:memory` | `0 5 * * 0` | Weekly communication metrics consolidation |

**Biofeedback** (enable if hardware present)

| Cron name | Schedule | What it runs |
|---|---|---|
| `relic:biofeedback-pull` | `5 4 * * *` | Zepp/Amazfit wearable data ingestion |
| `relic:biofeedback-gadgetbridge` | `10 4 * * *` | Gadgetbridge (Helio Ring) data ingestion |
| `relic:biofeedback-gb-ingest` | on-demand | Single Gadgetbridge file import |
| `relic:muse-aggregate` | `30 4 * * *` | Muse 2 EEG daily session aggregation |
| `relic:muse-recorder` | on-demand | Muse 2 EEG single session recorder |

**Weekly analysis**

| Cron name | Schedule | What it runs |
|---|---|---|
| `relic:liwc` | `0 3 * * 0` | Psycholinguistic (LIWC) word-category analysis |
| `relic:stress-index` | `0 6 * * 1` | Composite daily stress index computation |

**Optional integrations**

| Cron name | Schedule | What it runs |
|---|---|---|
| `relic:budget-bridge` | `20 4 * * *` | Actual Budget financial signal ingestion |
| `relic:voicenote` | on-demand | Voice note transcription → inbox |
| `relic:domain-prober` | on-demand | Targeted domain-coverage probe |
| `relic:backfill` | on-demand | Past-message JSONL import |
| `relic:motives` | on-demand | Implicit motive pattern inference |

**Monthly specialist analyzers**

| Cron name | Schedule | What it runs |
|---|---|---|
| `relic:schemas` | `0 5 1 * *` | Early Maladaptive Schema (EMS) detection |
| `relic:goals` | `30 5 1 * *` | Goal architecture and personal projects |
| `relic:sdt` | `0 6 1 * *` | Self-Determination Theory need assessment |
| `relic:portrait` | `0 6 1 * *` | Full narrative portrait synthesis |
| `relic:idiolect` | `0 4 1 * *` | Idiolect and linguistic fingerprint |
| `relic:caps` | `30 5 2 * *` | CAPS if-then behavioral signatures |
| `relic:attachment` | `0 5 3 * *` | Attachment style analysis |
| `relic:defenses` | `30 5 3 * *` | Defense mechanism detection |
| `relic:narrative` | `0 6 3 * *` | Narrative identity and self-story structure |
| `relic:appraisal` | `30 4 5 * *` | Cognitive appraisal pattern analysis |
| `relic:mental-models` | `0 5 5 * *` | Mental model and reasoning heuristic extraction |
| `relic:dual-process` | `30 5 5 * *` | System 1/System 2 balance estimation |
| `relic:constructs` | `0 6 5 * *` | Personal constructs (Kelly's Repertory Grid) |

---

## LLM provider

```env
RELIC_MODEL=claude-opus-4-6
RELIC_PROVIDER=anthropic
```

The `ProviderLLMClient` stub in `src/lib/provider_llm_client.py` reads these
values but does not implement the actual call - you must provide an adapter.
See [Adapters](ADAPTERS.md) for the implementation contract.

If `RELIC_MODEL` is empty, any cron that calls the LLM raises a clear
`RuntimeError` instead of a silent failure.

---

## Relational agent

```env
RELIC_RELATIONAL_AGENT=my-agent
```
OpenClaw agent name used for passive observation (`relic:passive-scan`)
and stress probes (`relic:checkin`). The passive scanner reads this
agent's session transcripts. Leave blank to disable passive observation.

```env
RELIC_RELATIONAL_AGENT_IDS=my-agent,alt-agent
```
Comma-separated list of additional agent IDs whose session directories are
also scanned. If omitted, only `RELIC_RELATIONAL_AGENT` is scanned.

---

## Optional integrations

```env
RELIC_ENABLE_TELEGRAM=true
```
Enables live check-in delivery via Telegram. Requires a Telegram channel
configured in OpenClaw. When `false`, the check-in cron generates the
question but does not send it.

```env
RELIC_ENABLE_BIOFEEDBACK=false
```
Enables physiological signal ingestion from Zepp/Amazfit wearables.
Requires credentials below.

```env
RELIC_ENABLE_MUSE=false
```
Enables Muse 2 EEG session aggregation via `relic:muse-aggregate`.
Requires `TELEGRAM_BOT_TOKEN` and the Telegram log channel vars below.

```env
RELIC_ZEPP_EMAIL=
RELIC_ZEPP_PASSWORD=
```
Zepp/Amazfit account credentials for the biofeedback adapter. Only read
when `RELIC_ENABLE_BIOFEEDBACK=true`. Store these in `.env` and keep
`.env` out of version control (it is in `.gitignore`).

```env
TELEGRAM_BOT_TOKEN=
```
Bot token for outbound Telegram messages (check-ins and Muse aggregate
notifications). Create a bot via [@BotFather](https://t.me/BotFather).
Required when `RELIC_ENABLE_TELEGRAM=true` or `RELIC_ENABLE_MUSE=true`.

```env
TELEGRAM_LOGS_CHAT_ID=
TELEGRAM_LOGS_THREAD_ID=
```
Telegram group/channel ID and optional topic thread ID where the Muse
aggregator sends daily EEG digests. Leave blank to suppress those
notifications without disabling the aggregator.

---

## Full `.env` example

```env
# Subject
RELIC_SUBJECT_ID=alice
RELIC_SUBJECT_NAME=Alice
RELIC_TELEGRAM_ID=123456789

# Paths
RELIC_DATA_DIR=~/.relic/alice
OPENCLAW_HOME=~/.openclaw
OPENCLAW_BIN=openclaw

# Check-in schedule
RELIC_CHECKIN_HOUR_START=9
RELIC_CHECKIN_HOUR_END=22
RELIC_CHECKIN_INTERVAL_MIN=30
RELIC_FOLLOWUP_CRON=relic:checkin-followup

# LLM provider (see docs/ADAPTERS.md)
RELIC_MODEL=claude-opus-4-6
RELIC_PROVIDER=anthropic

# Integrations
RELIC_ENABLE_TELEGRAM=true
RELIC_ENABLE_BIOFEEDBACK=false
RELIC_ENABLE_MUSE=false
RELIC_RELATIONAL_AGENT=my-agent
RELIC_RELATIONAL_AGENT_IDS=

# Biofeedback credentials (only if ENABLE_BIOFEEDBACK=true)
RELIC_ZEPP_EMAIL=
RELIC_ZEPP_PASSWORD=

# Telegram bot (required if ENABLE_TELEGRAM=true or ENABLE_MUSE=true)
TELEGRAM_BOT_TOKEN=
TELEGRAM_LOGS_CHAT_ID=
TELEGRAM_LOGS_THREAD_ID=
```
