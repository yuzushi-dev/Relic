# First Subject

!!! warning "Use synthetic data"
    This walkthrough uses synthetic demo data. Do not use real personal data unless you have explicit informed consent and your deployment meets the ethical requirements described in [Ethics](../ethics/index.md).

## What this produces

Running through the bootstrap process creates:

1. A Relic subject profile: facets, confidence scores, source data, consent records.
2. A Gumi diegetic profile: SOUL.md, initial MEMORY.md, background story.
3. A set of compiled runtime artifacts ready for injection.
4. A HermesProfile configuration for live delivery (if Hermes is configured).

These are written to `~/.relic/relic.db` and, for the Hermes-facing files, to `$HERMES_HOME/`.

## Creating a subject

```bash
relic subject create
```

This launches the bootstrap TUI. You can also specify IDs directly:

```bash
relic subject create --subject-id subj_demo_01 --experiment-id exp_synthetic
```

## Bootstrap steps

The TUI walks through these sections in order:

**1. Consent** — Records consent types and scope for the subject. This step is required; you cannot proceed without it.

**2. Self-report** — A set of open questions about personality, preferences, and relational style. In research use, these would be completed by the subject. In this demo, answer for the synthetic persona you are creating.

**3. Item battery** — Structured items drawn from the facet model. These produce initial trait estimates with labeled sources.

**4. Relational expectations** — What kind of relationship the subject expects with Gumi: communication frequency, tone, topics to avoid, and how they want Gumi to handle sensitive moments.

**5. Researcher-coded observations** — Qualitative observations from the researcher about the subject's behavioral style. These are labeled as researcher-coded and distinct from subject self-report.

**6. Boundaries** — Topics, types of content, or behaviors Gumi should not engage in with this subject.

**7. Delivery config** — If you are configuring live delivery, specify the platform (Telegram, WhatsApp) and contact details here. For a demo run, skip this.

**8. Gumi overrides** — Optional adjustments to the generated Gumi profile: name variations, specific aesthetic or character notes.

**9. Review** — A summary of the generated Gumi profile. This is the researcher's checkpoint to evaluate the calibrated relational distance before activating the subject. You can revise any step from here.

**10. First contact controls** — Settings for how Gumi will introduce herself: whether to reveal she has prior context about the subject, how much warmth to lead with.

## Checking the result

After bootstrap completes:

```bash
relic subject show subj_demo_01
```

This shows the subject's runtime status, active consent records, compiled artifact count, and Hermes profile hash. It does not show raw session keys.

## What to inspect

The generated Gumi profile is worth reading before you proceed. Check:

- Does the background story feel plausible for this subject?
- Is the relational distance calibrated — neither too similar nor completely alien?
- Are the stated boundaries respected in the SOUL.md?
- Is there anything in the inferred fields that looks like an over-reach?

To review the Gumi profile text directly, it will be at `$HERMES_HOME/SOUL.md` after bootstrap. If you are unhappy with it, re-run `relic subject create` with the same subject ID to go through the TUI again.

## Next steps

- [Hermes Integration](hermes-integration.md) — how to activate live delivery.
- [Researcher Workbench](researcher-workbench.md) — how to inspect and correct the profile after interaction.
- [Export and Deletion](export-and-deletion.md) — how to export or remove subject data.
