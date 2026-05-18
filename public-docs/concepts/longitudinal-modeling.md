# Longitudinal Modeling

Most agent personalization systems work with a static profile: a description written once, stored somewhere, and injected at the start of each conversation. Relic works differently. A subject profile is an evolving model built from evidence accumulated over time, with explicit tracking of what changed, why, and how confident the system is.

## Why static profiles fall short

A static character card or user summary captures a snapshot. It does not distinguish between what was true when it was written and what is true now. It does not represent uncertainty: either a trait is in the description or it is not. It cannot be partially corrected. And it treats all information sources as equivalent, collapsing self-report, researcher observation, and system inference into a single undifferentiated description.

For a system intended to adapt to a person over months or years, these limitations compound. An early characterization gets baked in. An incorrect inference cannot be specifically revoked. The subject has no visible model to contest.

## How Relic builds a profile

Profile construction has several distinct phases, and each phase is tracked separately:

**Bootstrap.** The initial profile is created through a structured process (`relic/profile/bootstrap_tui.py`) that collects baseline data across multiple dimensions: self-report, researcher-coded observations, item batteries, relational expectations, boundary preferences, and delivery configuration. Bootstrap data is labeled with its source and has its own confidence level.

**Passive interaction.** As the subject interacts with Gumi, the system captures behavioral signals. These are not stored as raw transcripts; they are processed through privacy and ingestion gates and accumulated as observations against specific facets.

**Active elicitation.** The system can ask targeted questions to fill gaps in the model. Elicited responses are labeled as such and distinguished from unprompted interaction.

**Correction.** The subject or researcher can correct any trait at any time. Corrections are authoritative: they propagate to all derived artifacts and cannot be overridden by subsequent inference.

**Review.** The researcher workbench provides visibility into the current model state, evidence sources, confidence scores, and pending corrections. Review decisions feed back into the pipeline.

## What a profile contains

At any point, a subject profile contains:

- Facet estimates: positions on theory-grounded bipolar spectra, each with a confidence score (0.0–1.0) and an observation count.
- Source references: which observations support which estimates.
- Correction state: any traits that have been explicitly corrected, and what they were corrected to.
- Confidence caps: upper limits on how confident the system can be about specific facets given the available evidence.
- Inferred fields: system-generated extensions of the profile that are held at low confidence and excluded from direct runtime injection.

The profile is not a description of the person. It is an approximation of their behavioral tendencies as observed in this interaction context, with all the limitations that implies.

## Runtime use

At runtime, the profile is compiled into artifacts that are injected as ephemeral context into Gumi's prompt. The compilation is deterministic and auditable. Artifacts are not written directly to Hermes memory; they are injected per-turn and traced. When the model is wrong, changing the underlying data and rerunning the compiler produces updated artifacts without leaving stale information in a persistent prompt.
