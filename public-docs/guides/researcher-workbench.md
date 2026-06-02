# Researcher Workbench

The researcher workbench is the oversight interface design for inspecting and correcting subject profiles. The current Python backend is a fixture-backed, read-only dashboard contract for study overview and subject registry data; full live backend wiring for every panel is not implemented in this artifact.

## Starting the workbench

```bash
relic ui
```

The current fixture-backed API can be exercised through the local UI/server code paths. Treat `relic ui` and browser hosting as deployment-specific until a live workbench backend is wired for your environment.

## What you can see

The workbench is organized around a subject view. For each subject you have access to:

**Subject overview**, current facet estimates with confidence scores, observation counts, and correction state. Color coding indicates confidence level and whether a facet has been manually corrected.

**Timeline**, the interaction event stream for a subject, organized by session. Events are shown with their ontological class, not raw content. Raw content access requires explicit researcher unlock.

**Review queues**, items flagged for researcher attention: low-confidence traits with new evidence, pending corrections, safety signal reviews.

**CAC traces**, for each turn, the scoring and filtering decisions the CAC made: which candidates were included, which were blocked, and why.

**Privacy traces**, what each privacy scan found and what was applied.

**Correction history**, all corrections that have been applied, when, by whom, and what changed.

**Artifact diffs**, what changed between compiler runs for a subject.

**Eval summaries**, aggregate metrics across sessions.

**Replication bundle status**, whether a replication bundle exists for the current artifact state.

## What you can do

The write surface is limited to:

1. **Submit a correction**: record a `researcher_feedback_event` targeting a specific trait or inference. The correction propagates through the pipeline automatically.
2. **Request a replay**: replay a session with different parameters for evaluation purposes.
3. **Create an eval case**: mark a specific interaction as an eval case for regression testing.

You cannot directly edit compiled artifacts, CAC traces, privacy traces, or lab outputs. See [Researcher Boundary](../concepts/researcher-boundary.md) for why.

## Submitting a correction

In the subject overview, each facet has a correction button. Clicking it opens a form to:
- Specify the corrected value or direction.
- Provide a reason (free text).
- Optionally attach evidence (e.g., a direct subject statement).

After submission, you will see the correction in the queue, and the system will schedule a recompile. The artifact diff will show what changed after the recompile completes.

## Permissions

Your access is scoped to the studies you are assigned to. You cannot see subjects from other studies. Study assignment is managed in `relic/ui/permissions.py`.

## Panel map (visual)

The workbench is organised into 12 panels. Layout is approximately:

```
+--------------------------------------------------------------+
| RELIC WORKBENCH    Subject: subj_demo_01   Researcher: dveri |
+---------+----------------------------------------------------+
|         |  +-- Subject Overview --------------------------+  |
|  NAV    |  |  facets, confidence, correction state        |  |
|         |  |  ------------------------------------------  |  |
| Overview|  |  [Correct]  [Reprovision]  [Export]          |  |
| Gumi    |  +----------------------------------------------+  |
| Hermes  |                                                    |
| Cron    |  +-- Timeline ----------------+ +-- Review Queue +  |
| Safety  |  |  sessions, events grouped  | | items flagged  |  |
| Constr. |  |  by trace_id or time       | | for attention  |  |
| Cont.   |  +----------------------------+ +----------------+  |
| Deliv.  |                                                    |
| Resume  |  +-- CAC Traces --------------+ +-- Corrections -+  |
| Eval    |  |  per-turn scoring,         | | history, who,  |  |
| Audit   |  |  factors, decision         | | when, why      |  |
| Export  |  +----------------------------+ +----------------+  |
|         |                                                    |
|         |  +-- Privacy Traces ----------+ +-- Artifact Diff+  |
|         |  |  redaction scans + outcomes| | before/after   |  |
|         |  +----------------------------+ +----------------+  |
+---------+----------------------------------------------------+
```

The 12 panels and what they expose (source: `relic/ui/workbench_panels.py`):

| Panel ID | Purpose | Permission |
|---|---|---|
| `subject_overview` | Facets, confidence, correction state, status | `READ_STUDY_OVERVIEW` |
| `gumi_profile` | SOUL.md preview, generation seed, overrides | `READ_ARTIFACT` |
| `hermes_profile` | Profile hash, plugin config snapshot | `READ_ARTIFACT` |
| `cron_proactivity` | Scheduled tasks, last fire times, decisions | `READ_QUEUE` |
| `safety_signals` | Tier/category, redacted evidence refs, aggregation state | `READ_QUEUE` |
| `behavior_constraints` | Label-stripped runtime patches in effect | `READ_ARTIFACT` |
| `shared_continuity` | Subject-confirmed markers, recall stats | `READ_ARTIFACT` |
| `delivery_allowlists` | Targets, expiry, platform | `READ_STUDY_OVERVIEW` |
| `session_resume` | Resume reconciliation state | `READ_STUDY_OVERVIEW` |
| `gumi_evaluation` | Per-subject eval scores | `READ_ARTIFACT` |
| `audit_log` | Every researcher action on this subject | `READ_QUEUE` |
| `exports_delete_forget` | Export/delete buttons + confirmations | `EXPORT_BUNDLE` (gated, not default) |

The `safety_signals` panel shows **redacted** evidence refs by default; raw evidence requires explicit researcher unlock and is logged as a forensic-mode access event.

## Workbench separation from runtime

The workbench is not in the Hermes runtime path. The current Python study API reads fixture data from `fixtures/researcher-workbench/study_overview.json` and exposes read-only routes for study overview and subjects. Panel/view-model modules define the intended separation, redaction, and permission contracts; live feedback/replay/write behavior must be wired and tested separately before use as an operational backend.
