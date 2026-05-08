# Cron Decision-Point Console Specification

## Status

Normative specification for PR27J.

## Purpose

Implement the subject-scoped cron decision-point console for the Researcher Workbench.

## Required Fields

| Field | Description |
|---|---|
| job_name | Name of the cron job |
| job_mode | Mode of the cron job |
| last_decision | NO_REPLY/blocked/candidate/deliver/error |
| reason_codes | Reason codes for decision |
| quiet_hours_state | Quiet hours status |
| rate_limit_state | Rate limit status |
| risk_state | Risk assessment status |
| delivery_attempted | Whether delivery was attempted |

## Follow-up Fields (PR33)

| Field | Description |
|---|---|
| followup_id | Unique follow-up ID |
| marker_id | Associated marker ID |
| due_after | Due timestamp |
| attempt_count | Current attempt count |
| max_attempts | Maximum allowed attempts |
| if_ignored | Action if ignored |
| status | Current status |

## Required Jobs

The following cron jobs must be visible:

- checkin
- followup
- proactive
- image
- audio
- music
- diegetic
- discovery
- nightly
- extract
- synthesize
- profile_sync
- healthcheck
- backup

## Decision Point Philosophy

Cron jobs are decision points, NOT guaranteed delivery.

Every cron run MUST record decision result:
- NO_REPLY
- blocked
- candidate
- deliver
- error

## Block Conditions

| Condition | Trigger |
|---|---|
| BLOCKED_CRON_WITHOUT_SUBJECT | Cron job not subject-scoped |
| BLOCKED_CRON_WITHOUT_DECISION_LOG | Decision not recorded |
| BLOCKED_CRON_DELIVERY_WITHOUT_GATE | Guaranteed delivery implied |
| BLOCKED_CRON_RATE_LIMIT_WITHOUT_AUDIT | Rate limit change without audit |

## Acceptance Criteria

- [ ] Cron jobs are subject-scoped
- [ ] Cron jobs are decision points, not guaranteed delivery
- [ ] Every cron run records decision result
- [ ] NO_REPLY count visible
- [ ] candidate count visible
- [ ] delivered count visible
- [ ] blocked count visible
- [ ] error count visible
- [ ] Rate limit change creates audit event
- [ ] All 14 required job types visible
