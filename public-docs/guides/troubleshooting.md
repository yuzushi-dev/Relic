# Troubleshooting

Common failures and how to recover. If a command is missing here, run it again with `RELIC_LOG_LEVEL=DEBUG` and read the structured log lines.

## First step for any problem

```bash
relic runtime doctor
```

This checks: Hermes connectivity, plugin registration, database access, Ollama model availability, delivery channel configuration. Most issues show up here.

## Installation

### `relic: command not found`

The `pip install -e .` did not put `relic` on your PATH, or you opened a new shell that has not seen it.

```bash
# Confirm where it ended up:
python -m relic --version

# If that works, add the user scripts directory to your PATH.
# Linux/macOS bash/zsh:
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

On Windows, `pip install` prints the install location; add it to PATH via *System Properties → Environment Variables*.

### `relic init` halts on Ollama install

`relic init` can install Ollama for you, but it needs `curl` and `bash`. If you are on Windows or the prompt fails, install Ollama by hand from [ollama.com/download](https://ollama.com/download), then re-run:

```bash
relic setup --check-only
relic setup
```

### `relic init` halts on Hermes install

Same story. Install Hermes by hand (see the URL printed in the error), then re-run `relic setup`.

### `pip install -e .` fails with `error: Microsoft Visual C++ 14.0 or greater is required` (Windows)

A dependency needs a C compiler. Install **Build Tools for Visual Studio** (workload: *Desktop development with C++*) or use Linux/macOS / WSL2.

## Subjects

### `relic subject create` exits midway

Bootstrap is resumable. Re-run with the same `--subject-id` and Relic will pick up where you left off:

```bash
relic subject create --subject-id subj_demo_01
```

To inspect a half-finished bootstrap:

```bash
relic-profile bootstrap resume <bootstrap_session_id>
```

The session ID is printed when bootstrap starts.

### `relic subject show` reports missing artifacts

Some artifacts were not compiled. Re-run provisioning:

```bash
relic subject reprovision <subject_id>
```

### `relic subject forget` refuses

Forget is irreversible and prompts for confirmation. To run in scripts:

```bash
relic subject forget <subject_id> --yes
```

## Runtime

### Gumi does not reply on Telegram

Walk through this list:

1. `relic runtime doctor`: confirm the plugin is registered and Hermes is up.
2. Confirm the subject's user ID is on the allowlist: `relic runtime allowlist list <subject_id>`.
3. Confirm the subject sent `/start` to the bot from their Telegram account at least once.
4. Confirm the bot token env variable is exported in the shell where Hermes runs. `relic subject show <subject_id>` flags missing tokens.
5. Check the Hermes gateway log for delivery errors.

### Gumi replies but without personalization

The plugin failed and fell back to SOUL.md only. Personalization is suppressed, not corrupted; nothing is lost. Check:

```bash
relic runtime doctor
RELIC_LOG_LEVEL=DEBUG relic runtime status
```

Common causes: `relic.db` not writable, Ollama not reachable, model not pulled.

### Images / voice / music do not generate

Confirm `GEMINI_API_KEY` is set in the environment Hermes runs under, and that quota is not exhausted. See [API Keys and Tokens](api-keys-and-tokens.md).

## Workbench

### `relic ui` shows a blank page

The static assets may not have been built. From the repo root:

```bash
cd ui && npm install && npm run build
cd ..
relic ui
```

If `npm` is unavailable, install Node.js 20+ from [nodejs.org](https://nodejs.org/).

### Workbench shows no subjects

The workbench reads from `RELIC_DB_PATH` (defaults to `~/.relic/relic.db`). If you ran bootstrap with a different `RELIC_DB_PATH`, the workbench will not see those subjects unless you launch it with the same value:

```bash
RELIC_DB_PATH=/path/to/relic.db relic ui
```

## Database

### `relic.db is locked`

Another process is writing. Quit that process (other `relic` commands, the workbench, the Hermes gateway). SQLite uses file locks; only one writer at a time.

### Schema mismatch

Relic migrates the schema automatically on startup. If a migration error appears, back up the file before doing anything else:

```bash
cp ~/.relic/relic.db ~/.relic/relic.db.bak.$(date +%s)
```

Then file an issue with the migration error output. Do not edit the file by hand.

## Logs

Set log level and format with environment variables:

```bash
RELIC_LOG_LEVEL=DEBUG RELIC_LOG_JSON=true relic runtime doctor
```

JSON logs are easier to grep when investigating a specific subject:

```bash
RELIC_LOG_JSON=true relic runtime status 2>&1 | jq 'select(.subject_id=="subj_demo_01")'
```

## Backup `relic.db`

`relic.db` is the single source of truth for all subject data on this machine. Back it up before any risky operation: schema migration, `forget`, `chronicle delete`, `relic init` rerun, OS upgrade.

### One-shot backup

```bash
mkdir -p ~/.relic/backups
cp ~/.relic/relic.db ~/.relic/backups/relic.db.$(date +%Y%m%dT%H%M%S)
```

Stop running `relic` / Hermes processes first so SQLite is not mid-write.

### Periodic backup (cron, Linux/macOS)

```bash
crontab -e
# add:
0 3 * * * /usr/bin/cp ~/.relic/relic.db ~/.relic/backups/relic.db.$(date +\%Y\%m\%d)
```

Prune older than 30 days:

```bash
find ~/.relic/backups -name 'relic.db.*' -mtime +30 -delete
```

### Full backup including profile directories

```bash
tar czf ~/relic-full-$(date +%Y%m%d).tar.gz ~/.relic ~/.hermes/profiles
```

### Restore

```bash
# Stop the Hermes gateway and the workbench first.
cp ~/.relic/backups/relic.db.<timestamp> ~/.relic/relic.db
relic runtime doctor
```

Restoring rolls back **all** subjects to the backup time. Per-subject restore is not supported.

## Reset (last resort)

To wipe local Relic state and start over:

```bash
# Stop any running Hermes gateway first.
rm -rf ~/.relic
rm -rf ~/.hermes/profiles/gumi-*
relic init
```

This deletes **all** subject data on the machine. There is no undo. Run `relic-profile export ...` and `chronicle export ...` for anything you want to keep first.
