# Ethics

Relic collects and processes behavioral data about real people. The ethical constraints described here are not peripheral — they shape the architecture, the data model, and the test suite. Ignoring them in a deployment is not a configuration choice; it breaks the system's core invariants.

## The core tension

Relic models observed interaction patterns and compiles them into runtime guidance for a conversational agent. This is useful precisely because it produces a personalized, evolving representation of a subject. It is dangerous for the same reason.

The system is designed around one principle: the model is not the person. A Relic profile is an inspectable, contestable approximation built from limited evidence. It has confidence scores because uncertainty is real. It has correction mechanisms because the model can be wrong. It has export and deletion because the person it represents retains authority over their own data.

## What the system does and does not claim

The facet model is grounded in established psychological frameworks — cognitive appraisal theory, attachment theory, self-determination theory, dual-process theory, CAPS, and LIWC. These are modeling dimensions, not clinical scales. Relic does not diagnose, screen, or assess mental health. A facet score is an estimate derived from behavioral signals in a limited interaction context. It should be treated as tentative, correctable, and domain-specific.

See [No Clinicalization](no-clinicalization.md) for the specific boundaries and the reasoning behind them.

## Constraints that apply to all deployments

- Use only synthetic or explicitly consented data.
- Do not deploy covert monitoring or profiling without participant knowledge and consent.
- Keep a hard separation between demo artifacts and real personal data.
- Do not let Gumi's diegetic events update the subject model. [Data Stream Separation](data-streams-separation.md) explains why this matters structurally.
- Support export, correction, pause, and deletion at all times. See [Consent and Control](consent-and-control.md).
- Do not design interaction patterns that foster exclusive attachment, dependency, or manipulative engagement. See [Behavioral Boundaries](boundaries.md).

## What happens when these constraints are violated

The test suite includes contract tests that enforce many of these constraints at the code level (`tests/ui/`, `tests/safety/`, `tests/shared-continuity/`). Some constraints are also architectural: the researcher UI cannot directly mutate compiled artifacts; safety signals cannot be exposed to subjects; unconfirmed continuity markers cannot be stored.

Where a constraint is aspirational rather than currently enforced in code, it is marked as such in the relevant documentation.
