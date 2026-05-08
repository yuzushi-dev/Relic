# Gumi Subject Runtime Provisioning Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make each Relic subject provision a functional private Gumi runtime profile with Telegram delivery configuration, subject-specific Hermes cron specs, visual/voice/Lyria canons, and safe dry-run/apply gates.

**Architecture:** Keep Relic subject state, Hermes private runtime state, secrets, generated media canons, and cron manifests separate. Relic writes redacted, inspectable subject artifacts; Hermes profile directories hold private `.env`, delivery config, cron specs, and workspace artifacts. Cron is split into maintenance jobs, initiative/delivery jobs, and media candidate jobs, each with independent policy gates.

**Tech Stack:** Python stdlib dataclasses/json/pathlib, argparse CLI, existing Relic profile registry, existing Gumi background generator, existing Hermes cron helper conventions, pytest.

---

## Current Gap

The current OSS implementation creates a subject and a private Hermes/Gumi shell, generates a minimal Gumi background, provisions `SOUL.md`, `USER.md`, `MEMORY.md`, `config.yaml`, `.env`, and composes/sends intro in dry-run.

Missing runtime pieces:

- Telegram bot token and Telegram user/chat id are not collected or provisioned.
- `--deliver` is blocked because no delivery provider config exists.
- `gumi_visual_canon.json` and `gumi_music_canon.json` are minimal derivations, not a full media/voice/Lyria contract.
- No `voice_canon`, `lyria_canon`, `media_policy`, or media-generation event log exists.
- PR22H cron exists only as generic maintenance scaffolding; it is not subject-specific.
- Initiative cron and Telegram delivery cron are not implemented.
- Existing cron outputs under `artifacts/gumi-roleplay/cron/` are correct for tests/reports but wrong for active subject runtime.

## Design Decisions

1. Treat PR22H as maintenance cron only. It must not block Gumi initiative/delivery cron.
2. Store actual secrets only in the private Hermes profile `.env`, never in Relic subject home or exports.
3. Treat Telegram user/chat id as a direct identifier. Store the usable value only in Hermes `.env`; store a hash/redacted display in Relic subject artifacts.
4. Core OSS tests must not require a live Telegram bot, Hermes daemon, cloud provider, image provider, voice provider, or Lyria provider.
5. `--apply` for cron creation must be guarded. Default path is `--dry-run`.
6. Prefer Hermes-native cron lifecycle commands when applying. Do not patch `jobs.json` except as a fallback repair path with explicit tests and docs.
7. Cron prompts must be self-contained because Hermes cron runs fresh sessions.
8. For delivery jobs, use Hermes delivery target/final response. Do not add a second `send_message` call to the same target.

## Target Layout

```text
$RELIC_HOME/subjects/<subject_id>/
  subject_profile.json
  consent_record.json
  delivery_policy.json
  delivery_decision_log.jsonl
  gumi_background_profile.json
  gumi_visual_canon.json
  gumi_voice_canon.json
  gumi_lyria_canon.json
  gumi_media_policy.json
  gumi_media_generation_log.jsonl
  gumi_cron_manifest.json
  provenance/

$HERMES_PROFILES_HOME/gumi-<subject_id>/
  .env
  config.yaml
  SOUL.md
  USER.md
  MEMORY.md
  workspace/gumi/
    background.json
    world.md
    relationship_policy.md
    visual_canon.json
    voice_canon.json
    lyria_canon.json
    media_policy.json
  cron/
    maintenance.yaml
    initiative.yaml
    media.yaml
    install_manifest.json
  workspace/gumi/cron/
    world_state_compaction_report.json
    continuity_candidate_review_report.json
    checkin_decision_log.jsonl
    delivery_decision_log.jsonl
    media_candidate_log.jsonl
```

## New CLI Surface

```bash
relic profile hermes configure-telegram <subject_id> \
  --bot-token-env GUMI_SUBJ_001_TELEGRAM_BOT_TOKEN \
  --telegram-user-id 123456789

relic profile gumi media generate <subject_id> --mode hybrid --seed 42
relic profile gumi media show <subject_id>

relic profile hermes cron provision <subject_id> --maintenance --initiative --media --dry-run
relic profile hermes cron provision <subject_id> --maintenance --initiative --media --apply
relic profile hermes cron list <subject_id>
relic profile hermes cron validate <subject_id>

relic profile gumi intro send <subject_id> --deliver
```

`--deliver` may succeed only when:

- subject status is `intro_composed`;
- contact channel is Telegram;
- consent allows contact;
- Telegram bot token env name is configured;
- token resolves in the private Hermes environment;
- Telegram user/chat id is configured;
- quiet hours and maximum contact frequency allow delivery;
- profile is not archived or withdrawn.

## Task 1: Delivery Policy Schema and Tests

**Files:**

- Create: `schemas/subject_delivery_policy.schema.json`
- Create: `tests/profile/test_delivery_policy.py`
- Modify: `relic/profile/registry.py`

**Steps:**

1. Write failing tests for `ProfileRegistry.configure_telegram_delivery`.
2. Assert it writes `delivery_policy.json` in the Relic subject home with no bot token and no raw token-like strings.
3. Assert it writes actual runtime values only to the Hermes profile `.env`.
4. Assert export redacts delivery identifiers.
5. Implement `DeliveryPolicy` dataclass with:
   - `subject_id`
   - `contact_channel`
   - `telegram_user_id_hash`
   - `telegram_user_id_display`
   - `telegram_bot_token_env`
   - `delivery_enabled`
   - `quiet_hours`
   - `maximum_contact_frequency`
   - `created_at`
   - `updated_at`
6. Implement `_hash_identifier` helper with SHA256.
7. Run:

```bash
PYTHONPATH=. python -m pytest tests/profile/test_delivery_policy.py -q
```

Expected final: passing tests, no raw token in subject artifacts.

## Task 2: Telegram Configuration CLI

**Files:**

- Modify: `relic/profile/cli.py`
- Test: `tests/profile/test_delivery_policy.py`
- Test: `tests/profile/test_gumi_hermes_cli.py`

**Steps:**

1. Write failing CLI test for:

```bash
relic profile hermes configure-telegram subj_001 --bot-token-env GUMI_SUBJ_001_TELEGRAM_BOT_TOKEN --telegram-user-id 123456789
```

2. Assert `.env` contains:

```text
TELEGRAM_BOT_TOKEN_ENV=GUMI_SUBJ_001_TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID=123456789
GUMI_DELIVERY_CHANNEL=telegram
```

3. Assert `delivery_policy.json` contains only hash/display values, not the full identifier if redaction policy chooses to hide it.
4. Implement parser under `hermes configure-telegram`.
5. Add validation:
   - subject exists;
   - subject not archived or withdrawn;
   - token env name matches `^[A-Z][A-Z0-9_]*$`;
   - user id is non-empty and not written to exports unredacted.
6. Run targeted tests.

## Task 3: Full Media Canon Generation

**Files:**

- Create: `relic/gumi/media.py`
- Create: `schemas/gumi_media_policy.schema.json`
- Create: `schemas/gumi_voice_canon.schema.json`
- Create: `schemas/gumi_lyria_canon.schema.json`
- Create: `tests/gumi/test_media_canon.py`
- Modify: `relic/profile/registry.py`
- Modify: `relic/profile/cli.py`

**Steps:**

1. Write failing tests that `generate_gumi_media_canon` creates:
   - `gumi_visual_canon.json`
   - `gumi_voice_canon.json`
   - `gumi_lyria_canon.json`
   - `gumi_media_policy.json`
   - Hermes workspace copies of each.
2. Define media canon as constraints, not generated assets:
   - visual style, negative prompts, allowed motifs, forbidden motifs;
   - voice persona, speech pace, timbre labels, no fixed scripts;
   - Lyria/music prompt constraints, mood palette, forbidden lyrical imitation;
   - provider policy with `provider_required=false` by default.
3. Ensure no actual image/audio/music generation is required in core tests.
4. Add CLI:

```bash
relic profile gumi media generate subj_001 --seed 42
relic profile gumi media show subj_001
```

5. Add validation that media canons exist for active or provisioned subjects.
6. Run:

```bash
PYTHONPATH=. python -m pytest tests/gumi/test_media_canon.py tests/profile/test_gumi_hermes_cli.py -q
```

## Task 4: Split Cron Models by Job Family

**Files:**

- Modify: `relic/gumi_plugin/cron_schedule.py`
- Create: `relic/gumi_plugin/cron_specs.py`
- Create: `tests/gumi_plugin/test_subject_cron_specs.py`
- Modify: `configs/hermes/cron/gumi-continuity.example.yaml`
- Create: `configs/hermes/cron/gumi-initiative.example.yaml`
- Create: `configs/hermes/cron/gumi-media.example.yaml`

**Steps:**

1. Preserve PR22H maintenance behavior.
2. Add `CronFamily` enum:
   - `maintenance`
   - `initiative`
   - `media`
3. Keep `send_messages` forbidden for `maintenance`.
4. Allow Hermes delivery only for `initiative`, gated by delivery policy.
5. Define allowed initiative jobs:
   - `gumi_first_contact_delivery`
   - `gumi_checkin_gap_probe`
   - `gumi_thread_followup`
6. Define allowed media jobs:
   - `gumi_media_candidate_review`
   - `gumi_visual_prompt_rollup`
   - `gumi_voice_prompt_rollup`
   - `gumi_lyria_prompt_rollup`
7. Tests must prove that:
   - maintenance job with delivery is invalid;
   - initiative job without delivery policy is invalid;
   - media job cannot call providers unless provider policy permits it;
   - all outputs render under subject Hermes home, not generic `artifacts/...`.

## Task 5: Subject-Specific Cron Spec Renderer

**Files:**

- Create: `relic/profile/cron_provisioning.py`
- Create: `tests/profile/test_subject_cron_provisioning.py`
- Modify: `relic/profile/registry.py`

**Steps:**

1. Write failing test for `render_subject_cron_specs(subject_id, families)`.
2. Expected outputs:

```text
$HERMES_HOME/cron/maintenance.yaml
$HERMES_HOME/cron/initiative.yaml
$HERMES_HOME/cron/media.yaml
$HERMES_HOME/cron/install_manifest.json
$RELIC_HOME/subjects/<subject_id>/gumi_cron_manifest.json
```

3. Maintenance spec:
   - `deliver: local`
   - success contract: `NO_REPLY` or `[SILENT]`
   - output paths under `$HERMES_HOME/workspace/gumi/cron/`
4. Initiative spec:
   - `deliver: telegram`
   - script precheck command points to deterministic local policy gate;
   - prompt is self-contained;
   - no explicit `send_message` duplicate.
5. Media spec:
   - default `deliver: local`;
   - provider calls blocked unless explicitly configured.
6. Manifest records:
   - subject id;
   - Hermes profile name;
   - family list;
   - dry-run/apply mode;
   - generated file paths;
   - created_at;
   - redacted delivery target.

## Task 6: Delivery Decision Gate

**Files:**

- Create: `relic/gumi/delivery.py`
- Create: `tests/gumi/test_delivery_decision_gate.py`
- Modify: `relic/profile/registry.py`

**Steps:**

1. Write tests for `DeliveryDecision.evaluate`.
2. Block when:
   - no consent;
   - archived/withdrawn subject;
   - missing token env;
   - missing Telegram chat id;
   - quiet hours active;
   - frequency cap exceeded;
   - intro not composed for first-contact delivery.
3. Allow when all gates pass.
4. Write `delivery_decision_log.jsonl` with:
   - no raw message text;
   - message hash only;
   - policy snapshot;
   - decision: `deliver`, `blocked`, `dry_run`, `no_reply`.
5. Add synthetic fixtures for quiet hours and frequency cap.

## Task 7: Cron Provision CLI

**Files:**

- Modify: `relic/profile/cli.py`
- Modify: `relic/profile/cron_provisioning.py`
- Test: `tests/profile/test_subject_cron_provisioning.py`

**Steps:**

1. Add CLI:

```bash
relic profile hermes cron provision subj_001 --maintenance --initiative --media --dry-run
relic profile hermes cron provision subj_001 --maintenance --initiative --media --apply
relic profile hermes cron list subj_001
relic profile hermes cron validate subj_001
```

2. Dry-run writes specs and manifests but does not invoke Hermes.
3. Apply mode checks:
   - `hermes` command available;
   - `HERMES_HOME` points to subject profile;
   - specs validate;
   - delivery policy valid if initiative selected.
4. Apply mode invokes Hermes lifecycle commands if available. Prefer command generation plus subprocess invocation with redacted logs.
5. If Hermes cron apply fails, return nonzero and write failure event to manifest/log without partial silent success.

## Task 8: First Contact `--deliver`

**Files:**

- Modify: `relic/profile/cli.py`
- Modify: `relic/gumi/initial_contact.py`
- Test: `tests/gumi/test_initial_contact.py`
- Test: `tests/profile/test_gumi_hermes_cli.py`

**Steps:**

1. Keep `--dry-run` behavior.
2. Change `--deliver` from unconditional block to policy-gated delivery.
3. In core tests, mock the delivery adapter. Do not require network.
4. Implement `TelegramDeliveryAdapter` as an interface plus dry-run/mock adapter first.
5. Live adapter can be optional and invoked only when:
   - env token resolves;
   - command has `--deliver`;
   - no dry-run flag;
   - delivery decision permits it.
6. Log delivery result with message hash and Telegram target hash only.

## Task 9: TUI Bootstrap Fields

**Files:**

- Modify: `relic/profile/bootstrap_tui.py`
- Test: `tests/profile/test_bootstrap_tui_flow.py`

**Steps:**

1. Add prompts for:
   - contact channel;
   - Telegram user id;
   - Telegram bot token env name;
   - consent for active elicitation;
   - consent for generated images;
   - consent for generated audio;
   - consent for generated music;
   - quiet hours;
   - maximum contact frequency.
2. Defaults must be safe:
   - delivery disabled unless Telegram fields are explicitly provided;
   - media generation canons created, but provider generation disabled;
   - cron provision dry-run only.
3. Tests verify the TUI writes delivery policy and media canons without live credentials.

## Task 10: Documentation and README

**Files:**

- Modify: `README.md`
- Modify: `docs/HERMES_PLUGIN_BOOTSTRAP.md`
- Create: `docs/GUMI_SUBJECT_RUNTIME_PROVISIONING.md`
- Create: `docs/GUMI_TELEGRAM_DELIVERY.md`

**Steps:**

1. Document first-run path:

```bash
relic profile init --subject-id subj_001 --experiment-id exp_001
relic profile hermes configure-telegram subj_001 --bot-token-env GUMI_SUBJ_001_TELEGRAM_BOT_TOKEN --telegram-user-id 123456789
relic profile gumi media generate subj_001 --seed 42
relic profile hermes cron provision subj_001 --maintenance --initiative --media --dry-run
```

2. Document what is safe to commit and what is local/private.
3. Document that live delivery requires explicit env setup and is not part of core OSS tests.
4. Document maintenance cron vs initiative cron vs media cron.

## Task 11: Public Verification

**Files:**

- Modify as needed: `scripts/ci/check_no_raw_private_data.py`
- Test: existing test suite

**Steps:**

1. Extend privacy scanner to detect:
   - Telegram token patterns;
   - raw Telegram id in exported subject artifacts;
   - raw media provider keys.
2. Run:

```bash
make lint
make test-docs
PYTHONPATH=. python scripts/ci/check_json_jsonl.py
PYTHONPATH=. python scripts/ci/check_no_raw_private_data.py
PYTHONPATH=. python scripts/validate_handoff.py
make test
```

Expected:

- all tests pass;
- no raw secrets;
- no root Markdown drift;
- no cloud provider required;
- dry-run cron provisioning works without Hermes.

## Acceptance Criteria

- Every subject can have an isolated Telegram delivery configuration.
- Real secrets never enter Relic subject home, exports, fixtures, logs, or README examples.
- Visual, voice, and Lyria canons are generated as structured constraints and copied into Hermes workspace.
- Subject cron outputs are under the private Hermes profile, not generic repo artifacts.
- Maintenance cron cannot send messages.
- Initiative cron can deliver only through policy-gated Hermes delivery.
- Media cron cannot generate provider assets unless consent and provider config allow it.
- `--dry-run` remains the default for cron provisioning and delivery tests.
- `--deliver` becomes functional behind explicit Telegram config.
- Full public test suite passes without live Telegram, Hermes cron daemon, image/audio/music provider, or network.

## Implementation Notes

- Use TDD for each task.
- Keep commits small by task.
- If using worker execution, use `codex exec --profile ollama-minimax-m27`; never use `ollama launch codex`.
- Do not route around review gates by weakening PR22H maintenance restrictions. Add a separate initiative cron family instead.
- Do not add real provider dependencies to core tests.
