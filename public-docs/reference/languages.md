# Languages

Where Relic, the TUI, the Gumi intro, and Gumi herself accept or produce text in a particular language. Use this when planning a non-Italian study.

## Quick map

| Surface | Languages | How to set |
|---|---|---|
| `relic` CLI help text | English | Hardcoded |
| Bootstrap TUI prompts | Mixed Italian + English | Mostly Italian, with English headings; not configurable in OSS |
| Subject self-report `language` field | Free string | Captured at bootstrap, used downstream as a Gumi prompting signal |
| Gumi intro message | `it` or `en` | `relic-profile gumi intro compose --language {it,en}` |
| Gumi runtime conversation | Subject-driven | Gumi responds in the language of the incoming turn |
| Workbench UI | English | Hardcoded |
| Chronicle / log lines | English | Hardcoded |

## Bootstrap TUI

The TUI was written for a primarily Italian-speaking research team. You will see prompts like:

```
GEMINI API KEY (per immagini, voce e musica)
  Chiavi GEMINI_API_KEY già configurate per altri soggetti:
    1. GEMINI_API_KEY = AIzaSy12...
    0. Inserisci nuova chiave
```

Headings tend to be English (`=== Subject Profile Bootstrap ===`, `--- Hermes Provisioning ---`); inline prompts and yes/no questions accept both forms (`y`/`yes`/`s`/`si`, `n`/`no`).

OSS does not ship a language switch for the TUI. If you need a fully English flow for an external researcher, plan a wrapper that translates the prompts at presentation time, or fork the strings under `relic/profile/_bootstrap_steps/`.

## Subject language field

At bootstrap (`relic/profile/_bootstrap_steps/self_report.py`), one of the descriptive fields is `language`, the subject's preferred natural language for conversation with Gumi. It is a free string by convention written as a BCP-47 tag (`it`, `en`, `it-IT`, `pt-BR`). It flows into:

- The Gumi background generation prompt (so Gumi's voice matches the subject's language).
- The intro composition default (`--language` overrides).
- The runtime conversation expectation (Gumi prompted to respond in that language).

It does **not** force Gumi to refuse other languages. Subjects can switch languages mid-conversation; Gumi will follow.

## Gumi intro

```bash
relic-profile gumi intro compose <subject_id> --language it     # default
relic-profile gumi intro compose <subject_id> --language en
relic-profile gumi intro send <subject_id> --deliver
```

Only `it` and `en` are accepted by the choices validator in `relic/profile/cli.py`. To add a third language:

1. Add the BCP-47 tag to the `choices` tuple on the `intro compose` and `intro send` subparsers.
2. Add the corresponding intro templates under `relic/gumi/` (or wherever the intro composer reads them).
3. Validate that the model selected can produce competent text in the new language.

## Gumi mid-conversation language switching

Gumi has no language gate at runtime. She uses the model's multilingual capability and the subject's `language` field as a soft prompt. Practical effects:

- A subject who writes a turn in French gets a French reply, even if `language=it`.
- The next turn returns to the subject's default if they switch back.
- Memory markers preserve the original language of the marker. Recall surfaces them verbatim; Gumi may paraphrase into the subject's current language.

If you need a hard gate (e.g. for a study restricted to one language), add a behavior policy patch via the plugin config that constrains output language. There is no built-in flag for this.

## Model and language quality

The default `qwen2.5:32b-instruct-q4_K_M` is competent in English, Italian, Spanish, French, German, and most major European languages. Quality drops on under-represented languages.

If you change the model ([Model Management](../guides/model-management.md)), run a small bilingual eval slice before committing to the new model in production. The eval harness does not include a language-quality metric out of the box, write one for your target language pair if it matters.

## What is **not** localised

- Error messages.
- Log lines (JSON or text).
- Chronicle event payloads (field names and enum values are English).
- Workbench UI labels.
- SOUL.md template scaffolding (the generated content matches Gumi's language, but the template comments are English).

A future internationalisation pass on the TUI and workbench is not on the public roadmap; track [`contributing/release-status.md`](../contributing/release-status.md) for changes.

## Recommendations

- **Italian-speaking team, Italian subjects:** use defaults; nothing to change.
- **English-speaking team, Italian subjects:** set `language=it` at bootstrap, run intro with `--language it`. Researchers read the workbench in English; the TUI in mixed IT/EN.
- **Mixed-language subjects:** set the subject's preferred default at bootstrap; rely on Gumi's mid-conversation following.
- **Non-IT/non-EN production studies:** fork the intro templates, validate model quality, write a study-specific behavior patch if you want a hard language gate.
