# Corrections and Replay

## Submitting a correction

Corrections are submitted through the researcher workbench UI or via the feedback event API. They are not applied by directly editing database records.

### Via the workbench

1. Open the subject overview.
2. Find the facet or inference to correct.
3. Click the correction button and fill in the corrected value and a reason.
4. Submit. The correction is queued and a recompile is scheduled.

### Via the API

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

See `relic/ui/feedback.py` for the full API.

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

The recompile is typically fast (seconds) unless many artifacts are affected. You can check recompile status in the workbench under the subject's artifact diff panel.

## Correction is authoritative

Once a correction is applied, the corrected value takes precedence. The memory dynamics layer, decay mechanisms, and graph activation cannot reinstate the original value. If new evidence comes in that contradicts the correction, it is flagged for researcher review rather than automatically updating the corrected facet.

## Viewing correction history

In the workbench, the correction history panel shows all corrections for a subject: what was corrected, when, by whom, what evidence was cited, and which artifacts were affected and subsequently updated.

Via CLI:

```bash
relic subject show <subject_id>
```

This shows correction counts and the most recent correction timestamp.

## Replay

A replay reruns a session with different parameters. Common uses: testing the effect of a correction, evaluating a new policy version against historical interaction, or generating eval cases.

### Requesting a replay from the workbench

In the session timeline, select a session and click "Request replay." You can modify:
- Which artifacts to use (current vs. a previous version).
- Which policy snapshot to apply.
- Whether to use a mock model for faster iteration.

### Via CLI

```bash
python scripts/eval_run.py --replay-session <session_id> --subject-id <subject_id>
```

Replay results are written to the eval summary and do not affect the live subject profile unless you explicitly promote them.

## Import corrections from external review

If corrections were annotated in an external review tool and exported as a JSONL file, import them:

```bash
relic subject import-corrections <subject_id> --file corrections.jsonl
```

Each line in the JSONL file is treated as a `researcher_feedback_event`. The format is defined in `relic/vault/import_corrections.py`. Imported corrections go through the same propagation pipeline as workbench corrections.
