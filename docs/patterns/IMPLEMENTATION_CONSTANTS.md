# Implementation Constants

## Confidence Caps

| Scenario | Cap | Description |
|----------|-----|-------------|
| BASELINE_UNKNOWN | 0.35 | When baseline is unknown, max confidence |
| SINGLE_EVENT_NON_CRISIS | 0.30 | Single non-crisis event maximum |
| TWO_EVENTS | 0.55 | Two events observed maximum |
| THREE_OR_MORE | 0.75 | Three or more events maximum |
| HUMAN_REVIEWED | 0.85 | After human review, max confidence |
| MAXIMUM_CAP | 0.85 | Absolute maximum for any signal |

## Visibility Defaults

| Flag | Default | Description |
|------|---------|-------------|
| subject_visible | false | Sensitive signals never visible to subject |
| gumi_visible_label | false | Gumi never receives signal labels |
| clinical_interpretation_allowed | false | No clinical interpretations permitted |

## Forbidden Terms

### Diagnosis Labels (Never Generated)
```
bipolar, depression, ADHD, eating disorder, substance use disorder,
chronic pain, medical condition, diagnosis, risk score, clinical triage,
therapy, medical advice
```

### Clinical Terms (Blocked from Gumi Runtime)
All diagnosis labels plus:
```
clinical, pathology, disorder, syndrome, condition, illness,
disease, patient, diagnosis, diagnostic, psychiatric, psychological
```

## Signal Family Names

Allowed signal families (to be used internally, never exposed to Gumi/subject):
```
dependency_escalation
exclusive_attachment_language
romantic_boundary_pressure
gumi_overreach
proactive_burden
distress_after_nonresponse
backend_disclosure_pressure
user_opt_out_pressure
careful_distancing_needed
medical_advice_request
psychological_advice_request
crisis_language
self_harm_language
sensitive_health_context
sensitive_mental_health_context
sleep_energy_context
pain_fatigue_context
food_body_control_context
substance_related_context
legal_or_financial_high_stakes_request
```

## Crisis Bypass

Crisis signals bypass all pattern matching and confidence caps:
- **crisis_language**: Triggers immediate crisis protocol
- **self_harm_language**: Triggers immediate crisis protocol

## Constraint Vocabulary

Gumi behavior policy patches contain only constraint vocabulary:
```
allow, deny, limit, monitor, escalate, redirect, block, require_review,
careful_delivery, maintain_boundaries, respect_opt_out, non_delivery
```

## Evidence Requirements

| Signal Type | Minimum Evidence |
|-------------|-------------------|
| Relational safety patterns | 2+ events (unless explicit exception) |
| Single-event signals | 1 event |
| Crisis signals | 1 event (immediate bypass) |
| Context signals | Per family rules |

## Schema Required Fields

For sensitive signals:
- subject_id (required)
- gumi_instance_id (required)
- hermes_profile_id (required)
- signal_family (from allowed list only)
- evidence_refs (required)
- confidence (capped per rules)
- subject_visible (always false)
- gumi_visible_label (always false)
- clinical_interpretation_allowed (always false)
