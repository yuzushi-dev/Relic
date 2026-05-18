# Limitations

This page documents the known limitations, epistemic constraints, and open research questions in Relic. Reading it before deploying or citing the system is recommended.

## Validity of the facet model

The frameworks underlying the facet model have established validity in research contexts. Relic's application of them does not.

Relic estimates facets from conversational interaction with a single agent in a specific relational context. This is a constrained observation window. The signals it captures are not equivalent to responses to standardized instruments, structured interviews, or behavioral observation across varied settings. Facet estimates should not be treated as generalizable personality measurements.

No normative data exists for Relic's facet estimates. There is no reference population, no test-retest reliability data, and no concurrent validity studies against established instruments. These are research questions that remain open.

## The interaction context shapes the model

Gumi is not a neutral observer. Her identity, communication style, and the relational context she establishes all influence how subjects behave in interaction with her. A subject who appears avoidant in attachment-relevant facets might be responding to something specific about Gumi's style, not expressing a stable general tendency.

This is a fundamental limitation of in-context behavioral modeling. It is not unique to Relic, but it is easy to forget when looking at a tidy facet score with a confidence value attached.

## Confidence scores are not calibrated probabilities

The confidence scores in Relic represent evidence accumulation, not calibrated probabilities of being correct. A confidence of 0.8 does not mean there is an 80% chance the facet estimate is accurate. It means the system has accumulated substantial evidence pointing in a consistent direction. Whether that evidence is representative, whether the direction is correctly labeled, and whether it generalizes outside the interaction context are separate questions.

## Correction does not eliminate uncertainty

Subject corrections are authoritative in the system: they propagate and override inferences. But a correction by the subject reflects their self-perception at a specific moment. Self-perception can differ from behavioral observation for well-documented reasons (social desirability, limited introspective access, context-dependence). Correction authority is the right design choice for consent and control reasons; it should not be read as epistemically settling the question.

## Safety signals are not risk assessments

Safety signals are contextual patterns detected in interaction. They are designed to trigger conservative behavior and researcher review, not to assess risk. The sensitivity settings for signal detection involve tradeoffs: higher sensitivity produces more false positives (researcher burden); lower sensitivity may miss genuine signals. Current settings have not been empirically calibrated against clinical outcomes because no such validation study has been conducted.

## Memory dynamics are not validated models of human memory

The memory dynamics layer (decay, reinforcement, association, consolidation) is inspired by memory research but is not a validated model of how human memory works. The parameters have been set based on design intuitions, not empirical fitting. They should be treated as an engineering choice that produces plausible-looking behavior, not as a scientific claim about memory processes.

## Scale constraints

The current SQLite backend is adequate for research deployments with tens to hundreds of subjects. For larger deployments, the PostgreSQL migration path exists but has not been tested at scale.

## What has not been studied

The following are known research gaps with no existing data from this system:

- Long-term interaction effects on the facet model (months to years).
- How Gumi's relational distance calibration affects outcomes across different subject populations.
- Whether the modeled facets predict anything outside the interaction context.
- The effect of safety signal governance on subject experience.
- Cross-cultural validity of the facet model as implemented.
- Adverse effects of extended interaction with a personalized relational agent.

## What this system should not be used for

- Clinical screening, assessment, or triage of any kind.
- Forensic or legal purposes.
- Employment, educational, or insurance decisions.
- Any context where the person being modeled has not given informed consent.
- Covert profiling.
- Drawing conclusions about populations from individual interaction data.
