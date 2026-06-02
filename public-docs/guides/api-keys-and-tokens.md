# API Keys and Tokens

How to obtain the credentials Relic asks for. Each section explains **what the key is for**, **how to get it**, and **how to give it to Relic**.

Relic stores keys as environment variables and as entries in a per-subject `.env` file under `$HERMES_HOME/`. Keys are never written to `relic.db`.

## Quick reference

| Key | Required when | Cost |
|---|---|---|
| Telegram bot token | Delivering messages over Telegram | Free |
| Telegram user ID | Delivering messages to a specific person | Free |
| `GEMINI_API_KEY` | Gumi sends images, voice notes, or music | Free tier available |
| `HINDSIGHT_LLM_API_KEY` | Using a non-Ollama LLM for Hindsight memory | Depends on provider |
| Memory provider keys (Byterover, Honcho, Holographic) | Using a hosted memory provider | Depends on provider |

For local-only research (no live delivery, no media), none of these are required. Ollama running locally is enough.

## Telegram bot token

Used by Gumi to send and receive messages on Telegram. One bot per subject is recommended so that subjects do not share a chat identity.

### 1. Create the bot

1. Open Telegram and search for `@BotFather`. It is an official account run by Telegram.
2. Send `/newbot`.
3. Pick a display name (any string the subject will see).
4. Pick a username ending in `bot`, e.g. `gumi_subj01_bot`. Must be unique across Telegram.
5. BotFather replies with a token like `123456789:ABCdefGHIjklMNOpqrSTUvwxYZ`. **This is the secret.** Treat it like a password.

### 2. Give it to Relic

The bootstrap TUI (`relic subject create`) will ask for the token at the **Delivery config** step. You can either paste it directly or set it in your shell first:

```bash
export GUMI_SUBJ01_BOT_TOKEN="123456789:ABCdef..."
```

The variable name is configurable. Relic suggests `GUMI_<SUBJECT_ID>_BOT_TOKEN`.

### 3. After bootstrap

The token is stored in `$HERMES_HOME/<profile>/.env`. To rotate it, edit that file and restart the gateway. To revoke it, send `/revoke` to BotFather.

## Telegram user ID

The numeric ID of the person who will receive Gumi's messages. Not the username.

### How to find it

The simplest way:

1. Open Telegram and search for `@userinfobot`.
2. Send it any message (e.g. `/start`).
3. It replies with your numeric ID, e.g. `123456789`.

Ask the subject to do this and send you the number.

### Give it to Relic

The bootstrap TUI asks for it at the **Delivery config** step. You can also add it later:

```bash
relic runtime allowlist add <subject_id> \
  --platform telegram \
  --target telegram:123456789
```

The subject ID is the identifier Relic generated (or the one you provided) during bootstrap.

## Gemini API key

Used when Gumi sends generated images, voice notes (TTS), or short music clips. Optional, text-only Gumi works without it.

### How to get one

1. Visit [https://aistudio.google.com/apikey](https://aistudio.google.com/apikey).
2. Sign in with a Google account.
3. Click **Create API key**. Pick an existing Google Cloud project or create one.
4. Copy the key. It looks like `AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX`.

Google's free tier covers light usage. Check the current quota at the link above; it changes.

### Give it to Relic

The bootstrap TUI asks for it after the delivery step. You can paste it then, or set it before running bootstrap:

```bash
export GEMINI_API_KEY="..."
```

Relic writes the key to `$HERMES_HOME/<profile>/.env`. To rotate it, edit that file and restart the gateway.

## Hindsight LLM API key

Hindsight is the embedded memory layer Relic configures by default. Out of the box it uses **Ollama running locally**, so no key is needed.

If you want Hindsight to use a hosted LLM instead (e.g. an OpenAI-compatible endpoint), set:

```bash
export HINDSIGHT_LLM_API_KEY="sk-..."
```

`relic init` will pick it up. The env variable name is configurable; the default is `HINDSIGHT_LLM_API_KEY`.

## Other memory providers (Byterover, Honcho, Holographic)

These are alternative memory backends. They are off by default. To switch:

1. Set `memory.provider: <name>` in the plugin config (`$HERMES_HOME/<profile>/plugins.yaml`).
2. Set the provider's API key as an environment variable. Each provider documents its own variable name and signup flow.

You will rarely need this. Hindsight + Ollama covers most research use.

## Security notes

- Tokens go in environment variables or `.env` files. They never go in `relic.db`, in commits, or in exported subject bundles.
- The `.env` files sit under `$HERMES_HOME/`. Keep that directory off shared drives.
- Rotating a token: edit the env variable / `.env` file and restart the gateway. No re-bootstrap needed.
- If a token is compromised, revoke it at the source (BotFather `/revoke`, Google Cloud console, provider dashboard) before anything else.

## When something does not work

- "Token not set" warnings on `relic subject show`: the env variable is not exported in the shell that will run Hermes. Add it to your shell profile or to `$HERMES_HOME/<profile>/.env`.
- Telegram bot does not reply: check that the subject sent `/start` to the bot at least once. Telegram refuses to deliver until then.
- Image / voice generation fails: confirm the Gemini key is set and that quota is not exhausted. See [Troubleshooting](troubleshooting.md).
