# No Clinicalization

Relic uses psychological frameworks to structure its facet model, but it is not a clinical tool. This distinction must be maintained consistently across all deployments, outputs, and communications about the system.

## What this means in practice

The system does not diagnose, screen, or assess mental health. It does not produce clinical scores, risk assessments, or psychiatric classifications. Facet values are modeling estimates derived from behavioral signals in a specific interaction context. They say something about how a subject tends to engage within this system; they do not generalize to clinical claims.

Terms the system does not use in subject-facing or runtime outputs:

- Names of diagnoses (depression, anxiety, bipolar disorder, ADHD, and any other clinical label)
- Clinical measurement instruments (PHQ, GAD, HAM, and similar scales)
- Risk scoring or triage language
- "Symptoms," "disorder," "condition," "pathology"

This applies to Gumi's language, to runtime artifacts, to exported data, and to any UI shown to subjects.

## The facet model is not psychometrics

The facet model draws from attachment theory, cognitive appraisal theory, self-determination theory, dual-process theory, CAPS, and LIWC. These are theoretical frameworks that have been validated in research contexts. Using them here does not mean Relic's measurements have the psychometric validity of the instruments those frameworks produced.

Relic's facets are:
- Derived from a limited interaction context, not a standardized assessment.
- Probabilistic estimates with explicit confidence scores, not normed scores.
- Correctable by the subject at any time.
- Not validated against clinical populations or outcomes.

The appropriate framing is always "modeling dimension" or "behavioral estimate," not "score" or "measurement."

## Safety signals

The system detects contextual patterns in interaction that may warrant adaptive behavior (for example, adjusting Gumi's tone or frequency of contact). These are called safety signals. They are visible to researchers only.

Safety signals are not diagnoses. The consent language for subjects explicitly states what the system does and does not claim. Researchers reviewing signals must not treat them as clinical assessments or use them to draw conclusions about a subject's health status.

The boundaries are enforced structurally: safety signals cannot appear in Gumi's outputs (`tests/ui/test_safety_signals_panel_contract.py`), cannot be included in subject exports, and cannot feed into shared continuity memory.

## Shared continuity memory

Gumi can remember things the subject has shared across sessions. The language Gumi uses to reference this memory must remain relational, not clinical:

Allowed: "I remember you mentioned that was hard for you." "You called it overwhelming last time."

Forbidden: "I've logged a pattern of low mood." "The system detected stress indicators."

The full list of forbidden runtime terms is maintained in `relic/shared_continuity/` and tested in `tests/shared-continuity/test_continuity_clinicalization_guard.py`.
