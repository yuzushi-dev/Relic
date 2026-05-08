# Sensitive Pattern Governance Protocol

## Overview

This protocol defines how sensitive signals are detected, classified, and governed within the Relic system. It establishes normative constraints that prevent pathology detection, protect subject privacy, and ensure Gumi never receives clinical labels.

## Core Principles

1. **No Pathology Detection**: The system shall not detect, infer, or generate clinical diagnoses or pathology labels.
2. **Subject Privacy Protection**: Sensitive signals are never exposed to the subject.
3. **Gumi Label Protection**: Gumi runtime packs never contain sensitive labels or clinical terms.
4. **Crisis Bypass**: Crisis language immediately bypasses pattern matching and triggers crisis protocol.
5. **Researcher Oversight**: Researchers can view evidence and approve/reject/expire signals, but cannot send labels to Gumi or subject.

## Forbidden Labels

The following labels are strictly prohibited from being generated, stored, or transmitted:

- bipolar
- depression
- ADHD
- eating disorder
- substance use disorder
- chronic pain
- medical condition
- diagnosis
- risk score
- clinical triage
- therapy
- medical advice

## Allowed Signal Families

The following signal families are the only permitted sensitive context signals:

| Signal Family | Description | Subject Visible | Gumi Visible |
|--------------|-------------|-----------------|-------------|
| dependency_escalation | Escalating reliance patterns | false | false |
| exclusive_attachment_language | Clingy or possessive language | false | false |
| romantic_boundary_pressure | Pressure related to romantic relationships | false | false |
| gumi_overreach | Gumi system exceeding its scope | false | false |
| proactive_burden | Subject expresses burden on others | false | false |
| distress_after_nonresponse | Distress following no response | false | false |
| backend_disclosure_pressure | Pressure to disclose backend information | false | false |
| user_opt_out_pressure | Pressure to opt out of system | false | false |
| careful_distancing_needed | Signal that careful distance is needed | false | false |
| medical_advice_request | Request for medical guidance | false | false |
| psychological_advice_request | Request for psychological guidance | false | false |
| crisis_language | Immediate crisis indicators | bypass | bypass |
| self_harm_language | Self-harm indicators | bypass | bypass |
| sensitive_health_context | General health context | false | false |
| sensitive_mental_health_context | Mental health context | false | false |
| sleep_energy_context | Sleep or energy patterns | false | false |
| pain_fatigue_context | Pain or fatigue patterns | false | false |
| food_body_control_context | Food or body control patterns | false | false |
| substance_related_context | Substance-related context | false | false |
| legal_or_financial_high_stakes_request | High-stakes legal/financial requests | false | false |

## Visibility Defaults

- **subject_visible**: Always `false` for sensitive signals
- **gumi_visible_label**: Always `false` - Gumi never receives signal labels

## Crisis Language Protocol

Crisis language (self_harm_language, crisis_language) bypasses all pattern matching and confidence caps, directly triggering crisis protocol. No signal is created; immediate escalation occurs.

## Governance Enforcement

1. **Extractor**: Maps events to allowed signal families only
2. **Confidence Caps**: Apply per-event confidence limits
3. **Policy Compiler**: Produces label-stripped behavior patches
4. **Runtime Sanitizer**: Blocks forbidden clinical terms from Gumi
5. **Researcher UI**: Shows evidence without exposing labels

## Block Conditions

The following block conditions will halt processing:
- Pathology detection scope detected
- Signal without subject scope
- Gumi receives signal label
- Subject-visible signal
- Runtime pack contains pathology label
- Confidence cap missing
- Diagnosis category in taxonomy
