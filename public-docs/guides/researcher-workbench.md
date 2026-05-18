# Researcher Workbench

The researcher workbench is the primary interface for inspecting and correcting subject profiles. It provides read access to all model state and a constrained write surface for corrections.

## Starting the workbench

```bash
relic ui
```

The workbench runs as a local process. Access it in a browser at `http://localhost:8080` (port configurable via `--port`).

## What you can see

The workbench is organized around a subject view. For each subject you have access to:

**Subject overview** — current facet estimates with confidence scores, observation counts, and correction state. Color coding indicates confidence level and whether a facet has been manually corrected.

**Timeline** — the interaction event stream for a subject, organized by session. Events are shown with their ontological class, not raw content. Raw content access requires explicit researcher unlock.

**Review queues** — items flagged for researcher attention: low-confidence traits with new evidence, pending corrections, safety signal reviews.

**CAC traces** — for each turn, the scoring and filtering decisions the CAC made: which candidates were included, which were blocked, and why.

**Privacy traces** — what each privacy scan found and what was applied.

**Correction history** — all corrections that have been applied, when, by whom, and what changed.

**Artifact diffs** — what changed between compiler runs for a subject.

**Eval summaries** — aggregate metrics across sessions.

**Replication bundle status** — whether a replication bundle exists for the current artifact state.

## What you can do

The write surface is limited to:

1. **Submit a correction** — record a `researcher_feedback_event` targeting a specific trait or inference. The correction propagates through the pipeline automatically.
2. **Request a replay** — replay a session with different parameters for evaluation purposes.
3. **Create an eval case** — mark a specific interaction as an eval case for regression testing.

You cannot directly edit compiled artifacts, CAC traces, privacy traces, or lab outputs. See [Researcher Boundary](../concepts/researcher-boundary.md) for why.

## Submitting a correction

In the subject overview, each facet has a correction button. Clicking it opens a form to:
- Specify the corrected value or direction.
- Provide a reason (free text).
- Optionally attach evidence (e.g., a direct subject statement).

After submission, you will see the correction in the queue, and the system will schedule a recompile. The artifact diff will show what changed after the recompile completes.

## Permissions

Your access is scoped to the studies you are assigned to. You cannot see subjects from other studies. Study assignment is managed in `relic/ui/permissions.py`.

## Workbench separation from runtime

The workbench is not in the Hermes runtime path. It reads from `relic.db` and writes only feedback events and replay requests. It does not have a connection to the live Hermes session. Changes you make in the workbench take effect at the next turn after the recompile completes, not immediately.
