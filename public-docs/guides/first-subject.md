# First Subject

!!! warning "Use synthetic data"
    This walkthrough uses synthetic demo data. Do not use real personal data unless you have explicit informed consent and your deployment meets the ethical requirements described in [Ethics](../ethics/index.md). A ready-to-adapt participant form is in [Consent Template](../ethics/consent-template.md).

## What this produces

Running through the bootstrap process creates:

1. A Relic subject profile: facets, confidence scores, source data, consent records.
2. A Gumi diegetic profile: SOUL.md, initial MEMORY.md, background story.
3. A set of compiled runtime artifacts ready for injection.
4. A HermesProfile configuration for live delivery (if Hermes is configured).

These are written to `~/.relic/relic.db` and, for the Hermes-facing files, to `$HERMES_HOME/`.

## Launch the wizard

```bash
relic subject create
```

You can also specify IDs upfront and skip the first prompts:

```bash
relic subject create --subject-id subj_demo_01 --experiment-id exp_synthetic
```

If `--subject-id` is omitted, the wizard auto-generates one like `subj_a1b2c3d4`. If you re-run with an existing subject ID, the wizard offers **[U]pdate**, **[N]ew ID**, or **[Q]uit** instead of overwriting.

## What the TUI looks like

The interface is plain text in the terminal. Each step prints a banner, a brief instruction, and one or more prompts. Answer at the cursor and press Enter.

```
=== Subject Profile Bootstrap ===

Enter subject ID:  [your input]
Enter experiment ID:  [your input]

=== Structured baseline battery ===
Researcher reads or paraphrases each item; subject responds;
researcher enters the value. Validated and project-derived items
are labelled separately.

────────────────────────────────────────────────────────────
Block: TIPI personality items
────────────────────────────────────────────────────────────
Item: I see myself as extraverted, enthusiastic.
Scale: 1 (Disagree strongly) to 7 (Agree strongly)
Response (1–7):  [your input]
... continues for the full battery
```

Inputs:

- **Free text:** type and press Enter. Blank is accepted only where defaults are documented.
- **Likert (1–N):** type the integer; the prompt repeats on invalid input.
- **Yes/no:** `y` / `n` / `yes` / `no` / `s` / `si`. Empty defaults to the suggestion shown in parentheses.
- **Multi-choice (e.g. [U]/[N]/[Q]):** type the first letter.

Press **Ctrl-C** at any prompt to abort. Bootstrap is resumable: re-run `relic subject create --subject-id <same-id>` and the wizard picks up after the last completed step. To inspect a checkpoint:

```bash
relic-profile bootstrap resume <bootstrap_session_id>
```

The bootstrap session ID is printed near the end of a successful run; for an aborted run, find it in `~/.relic/<subject_id>/bootstrap_session.jsonl`.

## The real step order

This is the order the wizard runs, matching `relic/profile/bootstrap_tui.py`. Numbers are the actual call sequence, not the human-friendly grouping in older docs.

| # | Step | Prompts you for | Source |
|---|---|---|---|
| 1 | Subject ID | identifier (auto if blank) | `bootstrap_tui.run_init` |
| 2 | Experiment ID | identifier (required) | `bootstrap_tui.run_init` |
| 3 | Structured item battery | TIPI + ECR-RS + project items, integer responses on a Likert scale | `_bootstrap_steps/item_battery.py` |
| 4 | Self-report descriptive fields | name, age, gender, language, timezone, contact channel, etc. | `_bootstrap_steps/self_report.py` |
| 5 | Researcher-coded fields | qualitative observations the researcher records, labelled separately from subject self-report | `_bootstrap_steps/researcher_coded.py` |
| 6 | Interaction preferences | message length, emoji use, time-of-day preferences, topics | `_bootstrap_steps/interaction_prefs.py` |
| 7 | Relational expectations | tone, continuity, disclosure stance, role Gumi should play | `_bootstrap_steps/relational_expectations.py` |
| 8 | Boundaries | topics or behaviors Gumi must not engage in, risk flags, escalation contact method | `_bootstrap_steps/boundaries.py` |
| 9 | Consent record | one explicit confirmation per consent type: memory storage, delivery, proactivity, media generation, etc. **No defaults**. | `_bootstrap_steps/consent.py` |
| 10 | Gumi overrides | optional researcher overrides for Gumi's name, signature emoji, aesthetic notes | `_bootstrap_steps/gumi_overrides.py` |
| 11 | Hermes provisioning | yes/no, provision a private Hermes profile now? | `bootstrap_tui.run_init` |
| 12 | Gemini API key | only if you ticked any media consent at step 9, paste or reuse from another subject | `_bootstrap_steps/delivery_config.collect_gemini_api_key` |
| 13 | Delivery config | only if you ticked delivery consent at step 9, Telegram user ID, bot token env var | `_bootstrap_steps/delivery_config.collect_delivery_config` |
| 14 | Gumi review loop | `accept` / `regenerate` / `abort` after seeing the generated Gumi background | `_bootstrap_steps/gumi_review.py` |
| 15 | First-contact controls | warmth, disclosure of prior context, first-message timing | `_bootstrap_steps/first_contact_controls.py` |

Notes:

- **Consent at step 9 gates the later steps.** Skipping delivery consent skips steps 12 and 13.
- **Item battery is administered first, before the descriptive fields.** This is intentional: scored constructs from the battery seed defaults for later steps.
- The "Gumi review loop" can be repeated. Hit `regenerate` until the Gumi background feels right, then `accept`.

## Checking the result

After bootstrap completes:

```bash
relic subject show subj_demo_01
```

Shows runtime status, active consent records, compiled artifact count, Hermes profile hash. Raw session keys are never displayed.

```bash
relic-profile show subj_demo_01      # full JSON dump
relic-profile validate subj_demo_01  # schema check
```

## What to inspect before going live

The generated Gumi profile is worth reading. Check:

- Does the background story feel plausible for this subject?
- Is the relational distance calibrated: neither too similar nor completely alien?
- Are the stated boundaries respected in SOUL.md?
- Is there anything in the inferred fields that looks like an over-reach?

To review the Gumi profile text directly: `$HERMES_HOME/<profile>/SOUL.md` after bootstrap. To regenerate, re-run `relic subject create` with the same `--subject-id`, choose **[U]pdate**, and pick `regenerate` at the Gumi review step.

## Back up before risky changes

Before any second bootstrap or schema migration, snapshot the database:

```bash
cp ~/.relic/relic.db ~/.relic/backups/relic.db.$(date +%Y%m%dT%H%M%S)
```

Full backup procedure: [Troubleshooting → Backup](troubleshooting.md#backup-relicdb).

## Next steps

- [Hermes Integration quickstart](hermes-integration.md#quickstart-from-bootstrap-to-first-message): activate live delivery and send the first message.
- [Daily Operations](daily-operations.md): what to do each day a subject is active.
- [Researcher Workbench](researcher-workbench.md): inspect and correct the profile after interaction starts.
- [Export and Deletion](export-and-deletion.md): export, pause, forget.
