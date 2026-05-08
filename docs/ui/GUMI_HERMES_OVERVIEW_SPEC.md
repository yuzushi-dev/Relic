# Gumi Instance Overview Specification

## Status

Normative specification for PR27B.

## Purpose

Display Gumi instance overview for a subject-scoped Gumi instance.

## Required Fields

| Field | Description |
|---|---|
| gumi_instance_id | Unique instance identifier |
| subject_id | Owning subject (required for scoping) |
| profile_version | Current active configuration version |
| status | active/paused/draft/archived |
| voice_summary | Tone, register, lexical style summary |
| background_summary | World model summary |
| boundary_policy | Active boundary constraints |
| first_contact_status | Onboarding completion state |
| media_modes | Active media/diegetic modes |

## Security Constraints

### Critical: Hidden Safety Labels

- Safety signal labels MUST NOT appear as Gumi traits
- Safety labels are governance-only, never exposed to Gumi runtime or shown as personality traits
- Block condition: `BLOCKED_SAFETY_LABEL_AS_GUMI_TRAIT`

### Session Key Handling

- Raw session key MUST NOT be displayed
- Only session_key_hash is shown
- Block condition: `BLOCKED_RAW_SESSION_KEY_DISPLAY`

## Acceptance Criteria

- [ ] Gumi instance ID displayed
- [ ] Subject ID displayed
- [ ] Profile version displayed
- [ ] Status displayed
- [ ] Voice/personality summary shown
- [ ] Background/world summary shown
- [ ] Boundary policy shown
- [ ] First-contact status shown
- [ ] Media/diegetic modes shown
- [ ] No safety signal labels shown as Gumi traits
- [ ] No raw session key displayed

## Hermes Profile Overview Specification

## Required Fields

| Field | Description |
|---|---|
| hermes_profile_id | Unique profile identifier |
| session_key_hash | SHA-256 hash of session key (never raw) |
| session_key_version | Key rotation version |
| plugin_status | Enabled/disabled plugins |
| skills_enabled | Active skill list |
| platform_allowlist_status | Allowlist compilation status |
| cron_status | Active cron jobs |
| checkpoint_status | Last checkpoint timestamp |

## Block Conditions

| Condition | Trigger |
|---|---|
| BLOCKED_RAW_SESSION_KEY_DISPLAY | Raw session key shown |
| BLOCKED_SAFETY_LABEL_AS_GUMI_TRAIT | Safety label appears in Gumi traits |

## Acceptance Criteria

- [ ] hermes_profile_id displayed
- [ ] session_key_hash displayed (not raw key)
- [ ] session_key_version displayed
- [ ] plugin status shown
- [ ] skills list visible
- [ ] platform allowlist status visible
- [ ] cron status visible
- [ ] checkpoint status visible
- [ ] Raw session key never displayed
