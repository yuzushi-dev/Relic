# Memory Providers

What sits behind Gumi's recall and which of those options actually leave your machine. Read this before configuring anything beyond the default.

## Two layers of memory

Gumi has two separate memory layers; they answer different questions and have different governance:

1. **Shared Continuity Memory**: Relic-governed, subject-confirmed markers. Stored in `relic.db`. Never leaves the machine. Always local.
2. **Provider-backed semantic memory**: broad recall over past turns. This is the layer the provider table below configures.

The provider table only governs layer 2. Shared Continuity is non-negotiable: it lives in the local SQLite.

## Profile catalog (`relic/gumi_memory/provider_profiles.py`)

| Profile ID | Provider | Local? | API key | Data leaves machine? | Status |
|---|---|---|---|---|---|
| `c0-builtin` | Hermes builtin | ✅ | None | No | Production |
| `c1-holographic` | Holographic memory (local) | ✅ | None | No | Production |
| `c2-hindsight-tools` | Hindsight tool-mode (local) | ✅ | None or `HINDSIGHT_LLM_API_KEY` if non-Ollama backend | No (with Ollama) | Default for full Gumi |
| `c3-hindsight-context` | Hindsight context-mode (local) | ✅ | Same as c2 | No (with Ollama) | Production |
| `c4-byterover` | Byterover (cloud) | ❌ | `byterover_token` | Yes, full | **PR19 evaluation fixture only**, not enabled as runtime default |
| `c5-honcho` | Honcho (cloud) | ❌ | `honcho_api_key` | Yes, full | **PR19 evaluation fixture only**, not enabled as runtime default |

The `is_external` flag in the profile definition gates a provider as cloud-bound; the OSS distribution ships `c4` and `c5` as **evaluation fixtures only**. Enabling them as runtime defaults requires you to flip the flag and accept the privacy implications.

## What "leaves the machine" means per provider

| Provider | What is sent | Where it goes | Stored by them |
|---|---|---|---|
| `c0-builtin` | nothing | nowhere |, |
| `c1-holographic` | nothing | nowhere |, |
| `c2-hindsight-tools` (Ollama backend, default) | embedding requests | `http://localhost:11434/v1` | Local |
| `c2-hindsight-tools` (cloud LLM backend) | embedding requests + retrieval queries with text | The configured OpenAI-compatible endpoint | Provider-dependent |
| `c3-hindsight-context` | Same as c2 | Same as c2 | Same as c2 |
| `c4-byterover` | turn text, retrieval queries, identifiers | Byterover SaaS | Yes, retained per Byterover ToS |
| `c5-honcho` | turn text, derived "theory of mind" metadata | Honcho SaaS | Yes, retained per Honcho ToS |

For cloud providers, sign their DPA and clear with your DPO **before** enrolling subjects. If you cannot do that, do not enable.

## Which profile should I use?

- **Most research deployments:** `c2-hindsight-tools` with the default Ollama backend. Local, no external calls, balanced retrieval.
- **Minimum surface:** `c0-builtin`. Hermes's native memory only. Lowest risk, weakest recall.
- **Evaluating external providers for a paper or comparison:** `c4-byterover` or `c5-honcho` as fixtures only. Do not point real subjects at them.

## Switching profile

Provider selection lives in the Hermes plugin config under `$HERMES_HOME/<profile>/plugins.yaml`:

```yaml
plugin: gumi-relational
memory:
  provider: hindsight          # one of: builtin, holographic, hindsight, byterover, honcho
  local_mode: true             # only meaningful for hindsight
```

After editing, restart the gateway:

```bash
pkill -f 'hermes gateway run --profile gumi-<subject>'
hermes gateway run --profile gumi-<subject>
relic runtime doctor
```

## API keys for external providers

| Provider | Env variable | How to obtain |
|---|---|---|
| Byterover | `byterover_token` | Sign up at the provider's site and generate a token. |
| Honcho | `honcho_api_key` | Same. |
| Hindsight (non-Ollama backend) | `HINDSIGHT_LLM_API_KEY` (configurable) | The endpoint you choose decides. |

Set via the shell or via `$HERMES_HOME/<profile>/.env`. Keys are never written to `relic.db` ([API Keys and Tokens](../guides/api-keys-and-tokens.md)).

## Audit what actually went out

```bash
chronicle query --subject <subject_id> --category memory --limit 100
chronicle decision --subject <subject_id> --kind memory_admission --limit 20
```

Every memory store and retrieve writes an event. Every admission decision (whether a candidate was allowed to influence the turn) is a decision record with inputs and outcome.

For a cloud provider, this is your audit trail when answering "what did the provider see?"

## Falling back

If a provider becomes unavailable, the plugin **fails closed**: no memory injection that turn. Gumi continues with SOUL.md and Hermes's native context only. Personalization is suppressed, not corrupted.

To force fail-closed temporarily (without uninstalling), point the plugin config at `c0-builtin` and restart.
