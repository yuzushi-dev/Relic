# Delivery Channels

What is actually wired vs. what the allowlist accepts. Read this before promising a participant a particular channel.

## Status at a glance

| Channel | Allowlist | Bootstrap setup | Live delivery | Notes |
|---|---|---|---|---|
| **Telegram** | ✅ | ✅ | ✅ | Default. Full bot integration via BotFather. |
| **WhatsApp** | ✅ (string accepted) | ❌ | ❌ | Allowlist accepts `whatsapp` but no delivery code path exists. Plan-only. |
| **Email** | ✅ (string accepted) | ❌ | ❌ | Allowlist accepts `email` but no delivery code path exists. Plan-only. |
| **SMS** | ⚠️ partial | ❌ | ❌ | Mentioned in boundaries collection only. No delivery. |

The `--platform` argument on `relic runtime allowlist add` is a free string with examples in its help text. Adding a non-Telegram entry does not by itself enable delivery.

## Telegram (production-ready)

Full setup: [API Keys and Tokens → Telegram bot token](api-keys-and-tokens.md#telegram-bot-token), then [Hermes Integration → Quickstart](hermes-integration.md#quickstart-from-bootstrap-to-first-message).

Summary:

1. Create the bot via `@BotFather` on Telegram.
2. Capture the bot token into an env var like `GUMI_<SUBJECT>_BOT_TOKEN`.
3. Find the subject's numeric Telegram user ID via `@userinfobot`.
4. `relic-profile hermes configure-telegram <subject_id> --bot-token-env ... --telegram-user-id ...`
5. `relic runtime allowlist add <subject_id> --platform telegram --target telegram:<id>`
6. Subject sends `/start` to the bot.
7. `hermes gateway run --profile gumi-<subject_id>`.

Per-subject bot recommended (no shared chat identity across subjects).

## WhatsApp (not implemented)

The allowlist data model treats `whatsapp` as a valid string, and the API includes it in examples, but there is **no** WhatsApp delivery adapter, no Business API integration, no token capture flow, no gateway path.

If you need WhatsApp:

- Decide whether you really need it. Telegram is operationally simpler and more permissive for research.
- If yes, write your own adapter. Start from `relic/hermes_adapter/identity.py` and `relic/hermes_runtime.py` and add a delivery target alongside the Telegram path. Plan for Business API approval (weeks-to-months lead time for templated outbound messages).
- Do not enrol WhatsApp-only subjects until the adapter is shipped and tested.

## Email / SMS (not implemented)

Same status as WhatsApp. The allowlist accepts the string; nothing reads it. No code path delivers via email or SMS.

If you only need **one-way notifications** to the researcher (not to the subject), use OS-level mechanisms (`mailx`, `cron` + a script). Do not pretend they are Gumi delivery channels.

## Platform string conventions

When `--platform` and `--target` are accepted, the conventions are:

| Platform | Target format | Example |
|---|---|---|
| `telegram` | `telegram:<numeric_user_id>` | `telegram:123456789` |
| `whatsapp` (placeholder) | `whatsapp:<E.164_number>` | `whatsapp:+393331234567` |
| `email` (placeholder) | `email:<address>` | `email:subj@example.com` |

The colon-prefixed form makes the target self-describing across platforms.

## How to know if delivery actually worked

```bash
relic runtime doctor                          # plugin + gateway health
relic runtime allowlist list <subject_id>     # entries present
chronicle decision --subject <subject_id> --kind delivery_gate --limit 5
```

The `delivery_gate` decision shows the outcome of each delivery attempt with the inputs that produced it (allowlist match, quiet hours, pause state, frequency cap).

## Roadmap

The platform abstraction was deliberately broader than the implementation so adapters can be added without schema changes. WhatsApp and email adapters are not on the public roadmap. Track [`contributing/release-status.md`](../contributing/release-status.md) for changes.
