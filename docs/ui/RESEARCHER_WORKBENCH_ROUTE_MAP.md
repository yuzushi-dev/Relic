# Researcher Workbench — Route Map

## Conventions

- `:study_id` — resolved from session/context (single-study deployment) or URL prefix.
- `:subject_id` — required for all subject-scoped and Gumi-instance-scoped routes.
- `:gumi_instance_id` — required for Gumi instance detail routes; must match subject's linked instance.
- `:version_id` — optional; targets a specific Gumi instance version.
- All routes are prefixed with `/workbench`.

---

## Study-Level Routes

| Route | View | Description |
|---|---|---|
| `/workbench` | Study Dashboard | Root; redirects to `/workbench/dashboard`. |
| `/workbench/dashboard` | Study Dashboard | Aggregate study overview, subject registry table. |
| `/workbench/subjects` | Subjects Registry | List of all enrolled subjects. |
| `/workbench/subjects/new` | Create Subject | Subject creation form. |
| `/workbench/subjects/import` | Import Subject | Subject import workflow. |
| `/workbench/gumi-instances` | Gumi Instances Index | Aggregate read-only index of all Gumi instances. No edit controls. |
| `/workbench/timeline` | Event Timeline | Cross-subject event feed (redacted). |
| `/workbench/inference` | Inference Review | Cross-subject inference review queue. |
| `/workbench/corrections` | Corrections | Cross-subject correction log. |
| `/workbench/risk` | Boundaries & Risk | Study-wide boundary violations and risk alerts. |
| `/workbench/cron` | Cron Console | All scheduled jobs and failure log. |
| `/workbench/artifacts` | Artifacts | Cross-subject artifact index. |
| `/workbench/exports` | Exports | Export queue and history. |
| `/workbench/settings` | Settings | Study-level configuration and access control. |

### Constraint

`/workbench/gumi-instances` is an index view. It has no nested edit or create routes. Any
action that targets a specific instance redirects to the subject-scoped route.

---

## Subject-Level Routes

All routes below require a valid `:subject_id`. Missing or invalid `:subject_id` → 404.

| Route | View | Description |
|---|---|---|
| `/workbench/subjects/:subject_id` | Subject Overview | Redirects to `.../overview`. |
| `/workbench/subjects/:subject_id/overview` | Subject Overview | Status card, linked Gumi instance, Hermes profile, risk level. |
| `/workbench/subjects/:subject_id/baseline` | Subject Baseline | Baseline enrollment and demographic data. |
| `/workbench/subjects/:subject_id/gumi` | Gumi Instance | Redirects to `.../gumi/identity`. |
| `/workbench/subjects/:subject_id/timeline` | Subject Timeline | Full-fidelity event timeline for this subject. |
| `/workbench/subjects/:subject_id/inference` | Subject Inference | Inference events and review queue for this subject. |
| `/workbench/subjects/:subject_id/corrections` | Subject Corrections | Correction log for this subject. |
| `/workbench/subjects/:subject_id/boundaries` | Subject Boundaries | Boundary definitions and violation history. |
| `/workbench/subjects/:subject_id/cron` | Subject Cron | Scheduled jobs scoped to this subject. |
| `/workbench/subjects/:subject_id/artifacts` | Subject Artifacts | Artifacts for this subject. |
| `/workbench/subjects/:subject_id/exports` | Subject Exports | Export packages for this subject. |
| `/workbench/subjects/:subject_id/audit` | Audit Log | Full audit trail for this subject. |

---

## Gumi Instance Routes (Subject-Scoped)

All routes below require both `:subject_id` and (implicitly) the subject's linked
`:gumi_instance_id`. The `gumi_instance_id` is resolved from the subject record, not from
the URL, to enforce subject scope. No Gumi instance edit route exists outside subject scope.

| Route | View | Description |
|---|---|---|
| `/workbench/subjects/:subject_id/gumi/identity` | Identity | Persona name, archetype, identity anchors. |
| `/workbench/subjects/:subject_id/gumi/voice` | Voice | Tone, register, lexical style, pacing. |
| `/workbench/subjects/:subject_id/gumi/world` | World | World model, lore, environment, culture. |
| `/workbench/subjects/:subject_id/gumi/body` | Body / Visual Canon | Physical description, visual reference canon. |
| `/workbench/subjects/:subject_id/gumi/relationships` | Relationships | Defined relationships for this Gumi instance. |
| `/workbench/subjects/:subject_id/gumi/routines` | Routines | Scheduled behavioral routines and proactive delivery. |
| `/workbench/subjects/:subject_id/gumi/modes` | Expressive Modes | Expressive mode definitions. |
| `/workbench/subjects/:subject_id/gumi/first-contact` | First Contact | First-contact script and onboarding configuration. |
| `/workbench/subjects/:subject_id/gumi/versions` | Versions | Version history, diff, rollback. |
| `/workbench/subjects/:subject_id/gumi/versions/:version_id` | Version Detail | Specific version snapshot view. |
| `/workbench/subjects/:subject_id/gumi/runtime-files` | Runtime Files | Runtime profile pack and file artifacts. |

### Gumi Route Constraints

- No route of the form `/workbench/gumi-instances/:gumi_instance_id/edit` exists.
- No route implies a singleton global Gumi runtime.
- All writes to Gumi instance data are routed through `/workbench/subjects/:subject_id/gumi/...`.

---

## Route Depth Summary

```
/workbench
  /dashboard                           — study level
  /subjects                            — study level
    /new                               — study level
    /import                            — study level
    /:subject_id                       — subject scope begins
      /overview
      /baseline
      /gumi                            — Gumi instance scope begins
        /identity
        /voice
        /world
        /body
        /relationships
        /routines
        /modes
        /first-contact
        /versions
          /:version_id
        /runtime-files
      /timeline
      /inference
      /corrections
      /boundaries
      /cron
      /artifacts
      /exports
      /audit
  /gumi-instances                      — aggregate index only, no edit
  /timeline                            — cross-subject, redacted
  /inference                           — cross-subject
  /corrections                         — cross-subject
  /risk                                — cross-subject
  /cron                                — cross-subject
  /artifacts                           — cross-subject, redacted
  /exports
  /settings
```

---

## Block Conditions Enforced by Routing

| Block Condition | Enforced By |
|---|---|
| `BLOCKED_GLOBAL_GUMI_RUNTIME` | No `/workbench/gumi-instances/:id/edit` route exists. |
| `BLOCKED_ROUTE_WITHOUT_SUBJECT_SCOPE` | All Gumi edit routes require `:subject_id` path segment. |
| `BLOCKED_MISSING_OBJECT_MODEL` | All route targets reference objects defined in `RESEARCHER_WORKBENCH_OBJECT_MODEL.md`. |
