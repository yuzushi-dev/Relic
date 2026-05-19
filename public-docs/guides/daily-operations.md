# Daily Operations

A cheat sheet for the routine ops you do once a deployment is live. Read [Hermes Integration](hermes-integration.md) first if you have not started a gateway yet.

## Each morning

```bash
# 1. Confirm runtime is healthy.
relic runtime doctor

# 2. Per-subject health snapshot.
relic-profile list
relic subject show <subject_id>

# 3. See what happened overnight.
chronicle timeline --subject <subject_id> --since $(date -d 'yesterday' -Iseconds) --limit 200
```

If `doctor` fails, see [Troubleshooting](troubleshooting.md).

## Reviewing a subject

```bash
# Open the workbench.
relic ui

# Or query the ledger directly:
chronicle query --subject <subject_id> --type cac_decision --limit 50
chronicle query --subject <subject_id> --type continuity_marker_confirmed --limit 50
chronicle decision --subject <subject_id> --kind admission_ruling --limit 20
```

In the workbench, prioritise the **Review queue** panel — items the system flagged for researcher attention.

## Pausing a subject for a sensitive period

From inside the subject's Hermes session, or via the workbench pause panel:

```
/relic pause
```

To resume: restart the session or use the workbench pause panel. See [Pause](export-and-deletion.md#pause).

## After a correction

```bash
# Confirm the correction landed and recompile finished.
relic subject show <subject_id>            # correction counts, latest timestamp

# Inspect what changed.
chronicle query --subject <subject_id> --type artifact_diff --limit 5
```

Recompile is automatic; you do not need to trigger it.

## Snapshot a subject (export)

```bash
relic-profile export <subject_id> --out ./snapshots/<subject_id>-$(date +%Y%m%d).json --redacted
chronicle export --subject <subject_id> --output ./snapshots/<subject_id>-$(date +%Y%m%d).tar.gz
```

Always use `--redacted` unless you have a specific reason not to. Raw text exports are opt-in.

## Backup `relic.db`

Before anything irreversible:

```bash
cp ~/.relic/relic.db ~/.relic/backups/relic.db.$(date +%Y%m%dT%H%M%S)
```

Full procedure: [Troubleshooting → Backup](troubleshooting.md#backup-relicdb).

## Restart Gumi cleanly

```bash
# Stop the gateway.
pkill -f 'hermes gateway run --profile gumi-<subject_id>'

# Run doctor to confirm it stopped.
relic runtime doctor

# Start again.
hermes gateway run --profile gumi-<subject_id>
```

The session resumes from disk state. Memory and continuity markers persist across restarts.

## Sending Gumi an out-of-band first message

If you missed the post-bootstrap send, or want to re-introduce Gumi after a long pause:

```bash
relic-profile gumi intro send <subject_id> --deliver
```

Dry-run version (no live delivery):

```bash
relic-profile gumi intro send <subject_id> --dry-run
```

## Process check-ins

If you enabled the longitudinal check-in pipeline:

```bash
relic checkin status --subject-id <subject_id>           # pending vs processed
relic checkin update-facets --subject-id <subject_id> --dry-run
relic checkin update-facets --subject-id <subject_id>    # apply
```

`--dry-run` shows the proposed facet updates before writing.

## Audit a delivery decision

```bash
chronicle decision --subject <subject_id> --kind cron_decision --limit 20
chronicle decision --subject <subject_id> --kind delivery_gate --limit 20
```

Every cron tick and delivery gate writes a decision event with the inputs (allowlist state, pause state, quiet hours, frequency cap) and the outcome.

## Weekly review checklist

- [ ] `relic runtime doctor` green.
- [ ] Backup created in the last 7 days.
- [ ] Review queue empty or triaged.
- [ ] No safety signals beyond the subject's stated boundaries.
- [ ] Allowlist entries still valid (no expired bot tokens, user IDs).
- [ ] Snapshot exported for every active subject.

If any item fails, fix before continuing the study.
