# Installation

> Tested on **Hermes**. Requires a running Hermes instance for hooks and cron registration.

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.12+ | Standard library only for core modules |
| Hermes | current | Required for hooks and cron registration |
| Node.js | 18+ | Required only for hook compilation (TypeScript → JS) |

---

## Option A - Wizard (recommended)

```bash
git clone https://github.com/yuzushi-dev/relic
cd relic
python install.py
```

The wizard walks through 9 steps:

1. Prerequisites check - Python, Hermes binary, version verification
2. Subject configuration - name, ID slug, Telegram sender ID
3. Runtime data directory - where the database, inbox, and portraits live
4. Hermes configuration - binary path, home directory, hooks directory
5. Check-in schedule - active hours and probe frequency
6. Optional integrations - relational agent, Telegram, biofeedback
7. Past-message backfill - import existing messages into the extraction inbox
8. Configuration summary - review before committing
9. Installation - writes files, compiles hooks, registers crons

**Dry run** (preview without writing anything):

```bash
python install.py --dry-run
```

---

## Option B - Manual setup

If you prefer to configure without the wizard, follow these steps.

### 1. Install the Python package

```bash
pip install -e .
```

### 2. Create `.env`

Copy the example and fill in your values:

```bash
cp .env.example .env
```

See [Configuration](docs/CONFIGURATION.md) for a full description of every variable.

### 3. Create the runtime data directory

```bash
mkdir -p ~/.relic/<your-subject-id>
touch ~/.relic/<your-subject-id>/inbox.jsonl
```

Set `RELIC_DATA_DIR` in `.env` to this path.

### 4. Compile and register hooks

Each hook is a TypeScript project. Hermes compiles it on registration.

```bash
# Register with Hermes (Hermes compiles TypeScript internally - no npm step needed)
hermes hooks enable relic-capture \
  --path ./hooks/relic-capture \
  --env RELIC_SUBJECT_ID=<your-subject-id> \
  --env RELIC_DATA_DIR=~/.relic/<your-subject-id>

hermes hooks enable relic-bootstrap \
  --path ./hooks/relic-bootstrap \
  --env RELIC_SUBJECT_ID=<your-subject-id> \
  --env RELIC_DATA_DIR=~/.relic/<your-subject-id>
```

### 5. Register cron jobs

Replace `<schedule>` with your values. The `checkin-followup` cron has no
fixed schedule - it is triggered on-demand by the capture hook.

```bash
PYTHON=$(which python3)
REPO=$(pwd)
DATA=~/.relic/<your-subject-id>
ENV="--env PYTHONPATH=$REPO/src --env RELIC_DATA_DIR=$DATA"

# Core pipeline
hermes cron add relic:extract \
  --command "$PYTHON -m relic.extract" \
  --cwd "$REPO" --schedule "0 */2 * * *" $ENV

hermes cron add relic:checkin \
  --command "$PYTHON -m relic.checkin" \
  --cwd "$REPO" --schedule "*/30 9-22 * * *" $ENV

hermes cron add relic:passive-scan \
  --command "$PYTHON -m relic.passive_scan" \
  --cwd "$REPO" --schedule "0 */6 * * *" $ENV

hermes cron add relic:reply-extract \
  --command "$PYTHON -m relic.reply_extract" \
  --cwd "$REPO" --schedule "0 */6 * * *" $ENV

hermes cron add relic:synthesize \
  --command "$PYTHON -m relic.synthesize" \
  --cwd "$REPO" --schedule "0 3 * * *" $ENV

hermes cron add relic:profile-sync \
  --command "$PYTHON -m relic.profile_sync" \
  --cwd "$REPO" --schedule "30 3 * * *" $ENV

hermes cron add relic:checkin-followup \
  --command "$PYTHON -m relic.checkin_followup" \
  --cwd "$REPO" --on-demand $ENV

# Daily enrichment
hermes cron add relic:entity-extract \
  --command "$PYTHON -m relic.entity_extract" \
  --cwd "$REPO" --schedule "0 4 * * *" $ENV

hermes cron add relic:decisions \
  --command "$PYTHON -m relic.decisions" \
  --cwd "$REPO" --schedule "15 4 * * *" $ENV

hermes cron add relic:healthcheck \
  --command "$PYTHON -m relic.healthcheck" \
  --cwd "$REPO" --schedule "0 4 * * *" $ENV

hermes cron add relic:memory \
  --command "$PYTHON -m relic.memory" \
  --cwd "$REPO" --schedule "0 5 * * 0" $ENV

# Weekly
hermes cron add relic:liwc \
  --command "$PYTHON -m relic.liwc" \
  --cwd "$REPO" --schedule "0 3 * * 0" $ENV

hermes cron add relic:stress-index \
  --command "$PYTHON -m relic.stress_index" \
  --cwd "$REPO" --schedule "0 6 * * 1" $ENV
```

For biofeedback, optional integrations, and all 13 monthly specialist analyzers see the full schedule in [docs/CONFIGURATION.md](docs/CONFIGURATION.md#cron-identifiers-reference). The wizard registers all crons automatically.

---

## Verify the installation

```bash
# Demo pipeline (no Hermes, no LLM required)
python -m relic.demo_runner --output-dir demo/generated
open demo/generated/demo_console.html

# Hermes status
hermes hooks status
hermes cron status

# Inbox
wc -l ~/.relic/<subject-id>/inbox.jsonl
```

---

## From demo to live data

The demo pipeline (`relic-demo`) writes synthetic data into `demo/generated/relic.db`.
The live pipeline writes real data into `~/.relic/<subject-id>/relic.db`.
These are separate files - the demo never touches your live database.

To switch the webui from demo data to live data, change `RELIC_DATA_DIR`:

```bash
# demo data (synthetic, no Hermes required)
RELIC_DATA_DIR=demo/generated HERMES_HOME=demo/generated python -m relic.webui --port 8765

# live data (requires installation + at least one extraction cycle)
RELIC_DATA_DIR=~/.relic/<subject-id> python -m relic.webui --port 8765
```

If you installed via wizard, `.env` already has `RELIC_DATA_DIR` set to your live directory:

```bash
source .env && python -m relic.webui --port 8765
```

The live database is populated by the cron pipeline. It will be empty until
`relic:extract` runs at least once and processes messages from `inbox.jsonl`.

---

## Connect an LLM

The extraction, check-in, and synthesis crons require an LLM. The demo
pipeline runs on keyword heuristics and needs no model.

See [Adapters](docs/ADAPTERS.md) for how to wire up a provider.

---

## Import past messages (backfill)

If you have existing messages you want the model to learn from, append them
to `inbox.jsonl` in the format below. The `relic:extract` cron will
process them on the next run.

```jsonl
{"message_id":"msg-001","from":"telegram:<subject-id>","content":"...","channel_id":"telegram","received_at":"2026-01-01T10:00:00Z"}
{"message_id":"msg-002","from":"telegram:<subject-id>","content":"...","channel_id":"telegram","received_at":"2026-01-02T09:15:00Z"}
```

The `from` field must match `telegram:<RELIC_SUBJECT_ID>` exactly.
`message_id` values must be unique across the file - duplicates are skipped.
