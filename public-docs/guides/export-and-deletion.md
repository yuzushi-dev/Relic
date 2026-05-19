# Export, Pause, Forget, Delete

Subjects can export their data, pause the system, and erase their data. Each operation maps to a specific command or API. The labels are deliberately distinct: **pause** is reversible, **forget** is irreversible.

## Export

Export a subject profile bundle. Lives on `relic-profile`, not `relic`.

```bash
relic-profile export <subject_id> --out ./export/<subject_id>.json [--redacted]
```

| Flag | Description |
|---|---|
| `--out` | Required. Output file path. |
| `--redacted` | Replace raw text with redaction markers. Safety signals always excluded. |

For event-level export (audit ledger as `tar.gz`):

```bash
chronicle export --subject <subject_id> --output ./export/<subject_id>.tar.gz
```

See [`chronicle export`](../reference/chronicle-cli.md#chronicle-export) for the full event-level export.

An audit event is written to `relic.db` on every export.

## Pause

Pause suspends Gumi's proactive behavior and CAC personalization without deleting anything.

### From the Hermes session (recommended)

Inside the Hermes session, call the researcher tool:

```
/relic pause
```

This sets the subject's pause state. Gumi keeps replying but does not run proactive cron tasks, and the CAC layer suppresses personalization until you resume.

To resume, restart the session or use the workbench pause panel.

### From Python (automation / scripts)

```python
from relic.control.pause import PauseController

pc = PauseController()
pc.pause(subject_id="subj_demo_01", reason="researcher_pause")
# ... later
pc.resume(subject_id="subj_demo_01")
```

API surface: `relic/control/pause.py`. There is no top-level `relic subject pause` CLI; the operation is performed from inside the Hermes session or from Python.

## Forget

Forget is the GDPR Art. 17 hard delete. **Permanently** erases all data for the subject on this machine. There is no undo.

```bash
relic subject forget <subject_id>          # prompts for confirmation
relic subject forget <subject_id> --yes    # skip prompt (automation only)
```

| Flag | Description |
|---|---|
| `--yes` | Skip the interactive confirmation. |

The command:

- emits an anonymised audit record (hashed `subject_id`) **before** erasure,
- removes the subject row from the registry,
- deletes the profile directory under `$HERMES_HOME/`,
- invalidates replication bundles and eval cases derived from the deleted data.

If you want to keep anything, run `relic-profile export ...` and `chronicle export ...` first.

## Session-scoped delete (chronicle ledger)

To delete a subject's events from the chronicle ledger only, use:

```bash
chronicle delete --subject <subject_id> --dry-run        # preview
chronicle delete --subject <subject_id> --cascade        # apply
```

See [`chronicle delete`](../reference/chronicle-cli.md#chronicle-delete). Always preview with `--dry-run` first.

## Consent revocation

To revoke specific consent types without a full erase, use the Python API:

```python
from relic.control.consent import ConsentManager, ConsentType

mgr = ConsentManager()
mgr.revoke_consent(ConsentType.MEMORY_STORAGE)
```

Revocation takes effect immediately. New interaction data is not processed under the revoked consent type.

## Operation matrix

| Goal | Command | Reversible | Audit event |
|---|---|---|---|
| Snapshot subject profile | `relic-profile export ... --out PATH` | n/a | yes |
| Snapshot audit ledger | `chronicle export --subject ID --output PATH` | n/a | yes |
| Suspend Gumi proactivity | `/relic pause` in Hermes session | yes | yes |
| Erase ledger only | `chronicle delete --subject ID --cascade` | no | yes |
| Erase everything (GDPR) | `relic subject forget ID` | no | yes (anonymised) |

## Before any irreversible operation

1. Run `chronicle export` and `relic-profile export --redacted` to a safe path.
2. Copy `relic.db` separately (see [Troubleshooting → Backup](troubleshooting.md#backup-relicdb)).
3. Confirm with the subject that the action matches their request.
4. Only then run `forget` or `chronicle delete --cascade`.
