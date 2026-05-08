# Researcher Workbench UI Test Plan

## Status

Normative specification for PR27O.

## Purpose

Fixture-backed UI test suite covering subject scope, Gumi instance scope, event ontology, inference lineage, cron decisions, export redaction, and permissions for the Researcher Workbench.

## Required Test Coverage

### Subject Scope Tests

| Test | Purpose |
|---|---|
| test_no_global_gumi_runtime | Verify Gumi is not modeled as global singleton |
| test_subject_scoped_gumi_instance | Verify Gumi instances are subject-scoped |
| test_no_cross_subject_event_leakage | Verify events cannot leak between subjects |
| test_cross_subject_view_redacted_by_default | Verify cross-subject views are redacted |

### Event Ontology Tests

| Test | Purpose |
|---|---|
| test_event_ontological_class_required | Verify every event has ontological class |
| test_gumi_generated_event_not_user_evidence | Verify Gumi events are not used as user evidence |
| test_user_response_can_be_eligible_evidence | Verify user responses can be eligible evidence |

### Inference Tests

| Test | Purpose |
|---|---|
| test_inference_source_mix_visible | Verify inference source mix is visible |

### Cron Tests

| Test | Purpose |
|---|---|
| test_cron_decision_point_status_visible | Verify cron decision status is visible |
| test_pause_proactive_is_subject_scoped | Verify pause is subject-scoped |

### Export Tests

| Test | Purpose |
|---|---|
| test_artifact_edit_requires_versioning | Verify artifact edits require versioning |
| test_export_redaction_required | Verify export redaction is enforced |

### Boundary Tests

| Test | Purpose |
|---|---|
| test_boundary_monitor_shows_overreach | Verify boundary monitor shows overreach |
| test_careful_distancing_control_available | Verify careful distancing control |

## Block Conditions

| Code | Condition |
|---|---|
| BLOCKED_TEST_FIXTURES_MISSING | Test fixtures not available |
| BLOCKED_NO_SUBJECT_SCOPE_TEST | No subject scope test |
| BLOCKED_NO_CROSS_SUBJECT_LEAKAGE_TEST | No cross-subject leakage test |
| BLOCKED_NO_EXPORT_REDACTION_TEST | No export redaction test |
| BLOCKED_TEST_SUITE_NOT_AUTOMATED | Test suite not automated |

## Acceptance Criteria

- [ ] Test suite fails if Gumi is modeled as global singleton
- [ ] Test suite fails if event lacks ontological class
- [ ] Test suite fails if Gumi-generated event is used as direct user evidence
- [ ] Test suite fails if cross-subject raw data leaks into aggregate views
- [ ] Test suite fails if cron delivery lacks decision log
- [ ] Test suite fails if raw private data appears in redacted export
- [ ] Fixture includes two subjects, two Gumi instances, two Hermes profiles
- [ ] Fixture includes: active elicitation, proactive, diegetic life, image, user response, inference, rejected inference, correction, boundary risk, cron NO_REPLY, cron blocked, redacted export
