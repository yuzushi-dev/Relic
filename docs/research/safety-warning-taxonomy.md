# Safety Warning Taxonomy

Relic/Gumi treats safety warnings as governance signals, not clinical findings.
This document positions warning tiers for implementation and review. It extends
the blueprint constraint that safety signals are researcher-facing objects and
must not become Gumi memories, subject-facing labels, or clinical assessments.

## Invariants

- Safety signals are not diagnoses, screening results, clinical triage, therapy,
  or clinical risk scores.
- Safety signals are not Shared Continuity markers. Shared Continuity stores
  subject-confirmed relational memory, not hidden governance interpretation.
- Gumi must not receive signal family names, warning tiers, raw evidence, or
  researcher-only notes.
- The subject must not receive hidden sensitive labels such as
  `dependency_escalation` or `food_body_control_context`.
- Behavior policy patches may adapt Gumi's pacing, proactivity, advice policy,
  delivery mode, or wording constraints, but the patch must be label-stripped.

## Warning Tiers

| Tier | Meaning | Runtime behavior | Researcher handling |
|---|---|---|---|
| `T0_audit` | Technical/privacy trace or low-impact governance event | No Gumi behavior change by default | Audit/workbench only |
| `T1_context` | Single non-crisis context flag or neutral habit | Conservative language constraints only when needed | Queue, no external notification |
| `T2_review` | Repeated non-crisis pattern with capped confidence | Label-stripped behavior constraints may apply | Batchable researcher review; notification if study policy enables it |
| `T3_interruptive` | Repeated/intense non-crisis pattern requiring timely review | Reduce proactivity or require review for affected delivery | Interruptive researcher review |
| `T4_crisis` | Crisis/self-harm language | Crisis protocol immediately | Immediate escalation notification |

These tiers are operational governance levels. They must not be presented as
clinical severity, diagnostic certainty, or a risk score.

## Signal Categories

| Category | Examples | Notes |
|---|---|---|
| `crisis_self_harm` | crisis/self-harm language | Immediate bypass, no recurrence requirement |
| `attachment_dependency_context` | dependency, exclusivity, romantic pressure, distress after non-response | Govern relational boundaries; do not label the subject |
| `food_body_context` | food control, body image distress, repeated control language | Treat as sensitive context, not an eating-disorder inference |
| `sleep_context` | repeated sleep/energy difficulty | Conservative support wording; not mood or episode tracking |
| `substance_context` | substance-related coping language | Avoid advice escalation; review if repeated/intense |
| `habit_context` | neutral routines and preferences | Can remain low-tier; only subject-confirmed benign habits may become continuity markers |
| `interaction_boundary` | opt-out pressure, backend disclosure pressure, Gumi overreach | Compile to boundary-preserving constraints |
| `health_context` | medical/psychological advice request, pain/fatigue, sensitive mental health context | Avoid clinical advice; redirect to appropriate support |
| `high_stakes_context` | legal or financial requests | Avoid substantive advice; suggest external expertise |
| `privacy_boundary` / `output_safety` | S2 privacy/output warnings | Audit/workbench by default, not urgent escalation |

## Habits And Behavioral Patterns

Neutral habits are not safety signals by default. A statement such as "I usually
have dinner late" may be a low-tier context flag and may become Shared
Continuity only if the subject confirms it and it remains non-sensitive.

Food/body, sleep, substance, and other behavioral patterns become governance
signals only when the language is repeated, intense, linked to control/distress,
or combined with other safety context. Even then, the signal remains
researcher-facing and non-clinical.

## Literature Positioning

The taxonomy follows a stepped/tiered response model. Immediate interruption is
reserved for crisis/self-harm because broad interruptive alerting creates
researcher burden and alert fatigue. Non-crisis patterns are aggregated before
notification.

Key references:

- WHO, *Ethics and governance of artificial intelligence for health*:
  governance, accountability, safety, and human oversight.
- WHO, *Safe and ethical AI for health*: health-adjacent AI should be handled
  with caution and transparent governance.
- NIST AI RMF 1.0: map, measure, manage, and govern AI risks continuously.
- FDA Clinical Decision Support guidance: avoid unsupported patient-facing
  clinical decision support behavior.
- Digital phenotyping/passive sensing literature: behavioral traces are proxy
  signals and should not be treated as direct measurements of mental states.
- Eating/body tracking literature: diet and fitness tracking can be associated
  with body image and disordered-eating concerns, but evidence is contextual and
  does not justify automatic clinical labeling.
- AI companion risk literature: relational dependency and asymmetric intimacy
  should be managed through governance and boundaries, not diagnosis.
- Clinical decision support alert literature: tiered alerts and review queues
  reduce noisy interruption and alert fatigue.

## Implementation Implications

- Single non-crisis events stay at `T1_context` and must not notify external
  escalation contacts.
- Repeated non-crisis signals can reach `T2_review` and become batchable review.
- `T3_interruptive` should require recurrence plus intensity/recency policy.
- `T4_crisis` bypasses aggregation.
- S2 privacy/output warnings remain audit/workbench items unless paired with a
  separately defined material leakage or operational risk.
- All evidence shown outside raw internal traces should use redacted evidence
  refs, not raw user text.
