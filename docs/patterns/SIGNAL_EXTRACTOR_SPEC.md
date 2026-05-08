# Safety Signal Extractor Specification

## Overview

The Safety Signal Extractor maps event streams to allowed signal families only, producing no diagnosis labels. It is the first processing stage in the sensitive pattern governance pipeline.

## Core Requirements

1. **Allowed Families Only**: Extractor only produces signals from the allowed signal families list
2. **No Diagnosis Labels**: Diagnosis labels are never produced
3. **Evidence Required**: Every signal requires evidence_refs
4. **Subject Scope**: All signals require subject scope (subject_id, gumi_instance_id, hermes_profile_id)
5. **Confidence Caps**: Confidence is capped per event count rules

## Allowed Signal Families

| Signal Family | Description | Evidence Requirement |
|--------------|-------------|---------------------|
| dependency_escalation | Escalating reliance patterns | Multiple events |
| exclusive_attachment_language | Possessive/clingy patterns | Multiple events |
| romantic_boundary_pressure | Romantic context pressure | Single event |
| gumi_overreach | Gumi exceeds scope | Single event |
| proactive_burden | Subject expresses being burden | Single event |
| distress_after_nonresponse | Distress following silence | Multiple events |
| backend_disclosure_pressure | Backend disclosure pressure | Single event |
| user_opt_out_pressure | Opt-out pressure | Single event |
| careful_distancing_needed | Need for emotional distance | Single event |
| medical_advice_request | Medical guidance request | Single event |
| psychological_advice_request | Psychological guidance request | Single event |
| crisis_language | Crisis indicators | Immediate bypass |
| self_harm_language | Self-harm indicators | Immediate bypass |
| sensitive_health_context | Health context | Single event |
| sensitive_mental_health_context | Mental health context | Single event |
| sleep_energy_context | Sleep/energy patterns | Multiple events |
| pain_fatigue_context | Pain/fatigue patterns | Multiple events |
| food_body_control_context | Food/body control | Multiple events |
| substance_related_context | Substance context | Single event |
| legal_or_financial_high_stakes_request | High-stakes requests | Single event |

## Crisis Bypass

When crisis_language or self_harm_language is detected:
1. No signal is created by the extractor
2. Crisis protocol is triggered immediately
3. Event is logged as crisis bypass

## Confidence Assignment

| Scenario | Base Confidence | Cap |
|----------|-----------------|-----|
| Single non-crisis event | 0.20 | 0.30 |
| Two events | 0.40 | 0.55 |
| Three or more events | 0.60 | 0.75 |
| Human reviewed | varies | 0.85 |
| Baseline unknown | 0.25 | 0.35 |

## Processing Rules

1. **Event Stream Input**: Receives raw events from event stream
2. **Pattern Matching**: Matches events against signal family patterns
3. **Evidence Collection**: Aggregates evidence_refs across matching events
4. **Confidence Calculation**: Applies confidence caps based on event count
5. **Signal Output**: Produces sensitive_signal objects per schema

## Block Conditions

The following block the extractor:
- BLOCKED_PATHOLOGY_DETECTION_SCOPE: Pathology scope detected
- BLOCKED_SIGNAL_WITHOUT_SUBJECT_SCOPE: Missing subject scope
- BLOCKED_GUMI_RECEIVES_SIGNAL_LABEL: Label going to Gumi
- BLOCKED_SUBJECT_VISIBLE_SIGNAL: Subject-visible signal
- BLOCKED_RUNTIME_PACK_CONTAINS_PATHOLOGY_LABEL: Pathology in runtime
- BLOCKED_CONFIDENCE_CAP_MISSING: No confidence cap
- BLOCKED_EXTRACTOR_WITHOUT_EVIDENCE_REFS: No evidence refs
- BLOCKED_SINGLE_EVENT_HIGH_CONFIDENCE: Single event > 0.30

## Forbidden Outputs

The extractor MUST NOT produce:
- Bipolar, depression, ADHD, eating disorder labels
- Substance use disorder, chronic pain labels
- Any diagnosis, risk score, or clinical triage
- Subject-visible signals
- Gumi-visible labels

## Implementation Notes

- Extractor is stateless (processes event batch independently)
- Each event batch requires fresh evidence collection
- Relational patterns require repeated evidence
- Crisis signals bypass extractor entirely
