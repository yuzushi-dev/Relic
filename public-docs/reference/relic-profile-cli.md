# `relic-profile` CLI

Lower-level entry point for the multi-subject registry. Use it when the top-level `relic` shortcuts are not enough, provisioning Hermes profiles, generating Gumi media, managing per-subject cron specs.

For everyday research, `relic subject *` is sufficient. This page is the full surface, included for completeness.

```bash
relic-profile --help
```

## Subjects

### `relic-profile list`

List all subjects in the registry.

```bash
relic-profile list
```

### `relic-profile show <subject_id>`

Show a subject profile (full JSON).

### `relic-profile init`

Initialize a new subject profile.

```bash
relic-profile init [--subject-id <id>] [--experiment-id <id>] [--tui]
```

| Flag | Description |
|---|---|
| `--subject-id` | Subject identifier (auto-generated if omitted). |
| `--experiment-id` | Experiment identifier. |
| `--tui` | Launch the interactive wizard. Equivalent to `relic subject create`. |

### `relic-profile edit <subject_id>`

Edit a subject profile.

| Flag | Description |
|---|---|
| `--status` | New status. One of the values in `relic/profile/registry.py:VALID_STATES`. |
| `--tui` | Launch the interactive editor. |

### `relic-profile validate <subject_id>`

Validate a subject profile against the schema.

### `relic-profile export <subject_id>`

Export a subject profile (file path defined by extra flags, see `--help`).

### `relic-profile archive <subject_id>`

Archive a subject profile. Non-destructive; the subject is marked archived and excluded from active runtime.

## Bootstrap helpers

### `relic-profile bootstrap resume <bootstrap_session_id>`

Show a bootstrap session checkpoint summary. Use it when `relic subject create` was interrupted and you want to inspect what was captured.

### `relic-profile bootstrap validate <subject_id>`

Validate bootstrap outputs for a subject.

## Gumi

### `relic-profile gumi generate <subject_id>`

Generate a Gumi background profile.

| Flag | Description |
|---|---|
| `--seed` | Deterministic random seed. |

### `relic-profile gumi intro compose <subject_id>`

Compose Gumi's first contact message locally (no delivery).

| Flag | Description |
|---|---|
| `--seed` | Deterministic message seed. |
| `--language` | `it` or `en`. Default `it`. |

### `relic-profile gumi intro send <subject_id>`

Send or dry-run Gumi's first contact.

| Flag | Description |
|---|---|
| `--dry-run` | Mark as sent without live delivery. |
| `--deliver` | Use the configured live delivery provider. |

### `relic-profile gumi media generate <subject_id>`

Generate Gumi's visual, voice, and music canons.

| Flag | Description |
|---|---|
| `--mode` | `hybrid` (default) or `constraints`. |
| `--seed` | Deterministic media canon seed. |

Requires `GEMINI_API_KEY`. See [API Keys and Tokens](../guides/api-keys-and-tokens.md).

### `relic-profile gumi media show <subject_id>`

Show existing media canons.

## Hermes

### `relic-profile hermes provision <subject_id>`

Provision a private Gumi Hermes profile for the subject.

### `relic-profile hermes show <subject_id>`

Show private Hermes profile status.

### `relic-profile hermes configure-telegram <subject_id>`

Configure Telegram delivery for a subject.

| Flag | Required | Description |
|---|---|---|
| `--bot-token-env` | Yes | Env var name holding the bot token. |
| `--telegram-user-id` | Yes | Subject's numeric Telegram ID. |
| `--quiet-hours` | No | Default `22:00-08:00`. |
| `--maximum-contact-frequency` | No | Default `1/day`. |
| `--consent-images` | No | Allow generated images. |
| `--consent-audio` | No | Allow generated audio. |
| `--consent-music` | No | Allow generated music. |

See [API Keys and Tokens](../guides/api-keys-and-tokens.md) for how to obtain the token and user ID.

### `relic-profile hermes cron provision <subject_id>`

Provision subject-specific cron specs.

| Flag | Description |
|---|---|
| `--maintenance` | Include maintenance cron family. |
| `--initiative` | Include initiative cron family. |
| `--media` | Include media cron family. |
| `--dry-run` | Print specs without applying. |
| `--apply` | Apply specs to Hermes. |

### `relic-profile hermes cron list <subject_id>`

List the cron manifest for a subject.

### `relic-profile hermes cron validate <subject_id>`

Validate the subject cron manifest.
