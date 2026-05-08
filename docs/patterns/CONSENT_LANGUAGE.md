# Consent Language for Sensitive Pattern Governance

## Overview

This document defines the consent language used when sensitive pattern detection is deployed. It ensures transparency about what the system does and does not claim.

## What the System DOES

### Claims (What the System Does)

1. **Context Signal Detection**: The system detects contextual patterns in user interactions that may indicate the need for careful delivery or adaptive responses.

2. **Safety Signal Generation**: The system generates safety signals based on interaction patterns to inform adaptive system behavior.

3. **Researcher Oversight**: Trained researchers review safety signals to make decisions about system adaptation.

4. **Confidence Scoring**: Signals are assigned confidence levels based on evidence quantity and baseline comparison.

5. **Constraint Application**: The system applies constraint-based adaptations to maintain appropriate boundaries.

## What the System Does NOT Claim

### Health Monitoring Claims (FORBIDDEN)

The system does NOT claim to:

- Monitor, detect, or track health conditions
- Diagnose mental health or medical conditions
- Detect "depression", "anxiety", "bipolar disorder", "ADHD", or any diagnosis
- Provide clinical assessments or risk scores
- Act as a medical or psychological tool
- Replace professional healthcare or mental health services

### Diagnosis Claims (FORBIDDEN)

The system does NOT claim to:

- Diagnose any medical or mental health condition
- Detect "eating disorders", "substance use disorders", or "chronic pain"
- Provide clinical triage or risk scoring
- Make psychiatric or psychological assessments
- Identify "medical conditions" or "diagnoses"

## Consent Language Template

### For Subjects

```
CONSENT FOR CONTEXTUAL SAFETY SYSTEM

This system uses contextual safety signals to inform adaptive responses.
These signals are based on interaction patterns and researcher review.

IMPORTANT: This system does NOT:
- Diagnose mental health or medical conditions
- Monitor health status
- Provide clinical assessments
- Replace professional healthcare

Safety signals are reviewed by trained researchers only.
Signal labels are never shared with the subject or exposed in outputs.
```

### For Researchers

```
RESEARCHER CONSENT

As a researcher, you will review safety signals that indicate
contextual patterns requiring adaptive system responses.

Your role:
- Review evidence for safety signals
- Approve, reject, or expire signals
- Ensure signals are handled appropriately

You must NOT:
- Share signal labels with subjects
- Send signal information to Gumi or subject-facing systems
- Override visibility protections

The system is designed to protect subject privacy while enabling
researcher oversight of adaptive behaviors.
```

## Block Conditions

The following block conditions prevent consent violations:
- BLOCKED_CONSENT_CLAIMS_HEALTH_MONITORING
- BLOCKED_CONSENT_CLAIMS_DIAGNOSIS

## Implementation Notes

- Consent language must be displayed before system activation
- No claims about health monitoring or diagnosis are permitted
- All signals are subject-scoped
- Researcher actions are logged
- Signal labels never reach Gumi or subject
