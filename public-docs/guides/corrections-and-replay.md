# Corrections and Replay

A correction tells Relic "this trait/inference is wrong, replace it with this." Corrections are authoritative: once applied, they take precedence over all later evidence unless explicitly contradicted.

## Submitting a correction (UI: recommended)

1. Open the researcher workbench: `relic ui`, then `http://localhost:8080`.
2. Open the subject view.
3. Find the facet or inference to correct.
4. Click **Correct**, fill in the corrected value and the reason, optionally cite an evidence reference (e.g. `session_04_turn_12`).
5. Submit. The correction is queued and a recompile is scheduled.

The correction history panel shows every correction with who, when, why, and which artifacts were touched.

## Submitting a correction (Python: automation)

```python
from relic.ui.feedback import submit_researcher_feedback

submit_researcher_feedback(
    subject_id="subj_01",
    target_type="facet",
    target_id="autonomy_orientation",
    corrected_value={"direction": "high", "confidence": 0.7},
    reason="Subject explicitly stated preference for self-direction in session 4",
    evidence_ref="session_04_turn_12",
)
```

Full surface: `relic/ui/feedback.py`.

## Importing corrections from external review

If corrections were annotated externally (CSV/JSONL from a review tool), they can be imported via the Python API. There is no `relic` CLI wrapper for this.

```python
from pathlib import Path
from relic.vault.import_corrections import import_correction_directory

result = import_correction_directory(Path("./external_review/"), dry_run=False)
print(result)
```

Single-file variant: `import_correction_note(note_path, dry_run=False)`.

API: `relic/vault/import_corrections.py`. Imported corrections go through the same propagation pipeline as workbench corrections.

## What happens after a correction

```
researcher_feedback_event written
  -> relic/correction/propagation.py identifies affected artifacts
  -> affected artifacts marked stale
  -> recompile queued
  -> relic/compiler/pipeline.py reruns
  -> new artifacts written to relic.db
  -> CAC uses updated artifacts at next turn
```

Recompile is typically a few seconds. Check status in the workbench under the subject's artifact diff panel.

## Correction is authoritative

Once a correction is applied, the corrected value takes precedence. Memory dynamics, decay, and graph activation cannot reinstate the original value. If new evidence contradicts the correction, the new evidence is **flagged for researcher review** rather than silently overwriting the corrected facet.

## Viewing correction history

In the workbench, the correction history panel shows all corrections for a subject.

Via CLI:

```bash
relic subject show <subject_id>
```

Reports correction counts and the most recent correction timestamp.

## Replay

A replay reruns a session with different parameters. Used for: testing a correction's effect, evaluating a new policy snapshot against historical interaction, generating eval cases.

### From the workbench

In the session timeline, select a session and click **Request replay**. You can modify:

- Which artifact version to use (current vs. a previous version).
- Which policy snapshot to apply.
- Whether to use a mock model for faster iteration.

### From CLI

```bash
python scripts/eval_run.py --replay-session <session_id> --subject-id <subject_id>
```

Replay results are written to the eval summary. They do **not** affect the live subject profile unless you explicitly promote them.
