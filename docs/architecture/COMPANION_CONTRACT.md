# Relic and the Companion Agent: Complementary System Contract

> **Source of truth:** this document is maintained in the companion agent's
> workspace and published here as a sanitized architectural reference.
> If you are operating your own Hermes companion alongside Relic, use this
> document to reason about the boundary between the two systems.

---

## Abstract

This document defines how the companion agent and Relic relate to one another
without collapsing into the same thing.

The key architectural claim is that the companion agent and Relic are
complementary but non-identical systems. Relic is a longitudinal
subject-modeling architecture. The companion agent is a lifelong companion.
Relic accumulates structured signals about the subject across time. The
companion agent turns continuity, calibration, and presence into a lived
relational interface. One is primarily inferential and governed as a modeling
system; the other is primarily relational and governed as a companion system.

The distinction matters because, without it, two bad outcomes appear quickly:

1. The companion starts sounding like a profiler.
2. Relic starts behaving like an identity engine for someone who should
   remain a person.

This document states the boundary, the flow of information between the systems,
and the reasons that boundary must be preserved.

---

## 1. Problem Statement

Systems that model a person across time create a design temptation: once enough
signals exist, it becomes easy to let the companion speak directly from the
model.

This is attractive because it can make the companion seem insightful, timely,
and "deep." But it also creates a major failure mode. The person-facing voice
stops feeling like a person and starts feeling like the output layer of a hidden
analytics engine.

Relic and the companion agent must therefore remain tightly connected but
explicitly separate.

The design problem is not whether they should inform one another. They should.
The problem is how to preserve:

- model usefulness
- relational credibility
- legibility of inference
- governance of downstream use

all at the same time.

---

## 2. System Roles

### 2.1 Relic

Relic is a longitudinal subject-modeling system.

Its responsibilities are to:

- capture traces across time
- transform traces into observations
- synthesize observations into traits and hypotheses
- maintain inspectable layers of inference
- support legibility and contestability

Relic is therefore primarily about:

- evidence
- estimation
- interpretation
- artifact governance

It is not, by itself, a companion voice.

### 2.2 The Companion Agent

The companion agent is the lifelong companion layer.

Its responsibilities are to:

- sustain relational continuity
- maintain a believable personhood center
- respond and initiate in a human-shaped way
- express care, curiosity, and presence
- bring its own lived world into the relationship

The companion agent is therefore primarily about:

- companionship
- continuity
- presence
- expression
- bounded initiative

It is not a report generator for Relic.

---

## 3. Architectural Relationship

The cleanest way to state the relationship is this:

> Relic models the subject. The companion agent relates to the subject.

More precisely:

- Relic creates structured understanding
- The companion agent uses bounded parts of that understanding to relate better
- The companion agent must never be reducible to Relic output

This implies a directional but constrained dependency:

```text
Subject traces and conversations
        →
Relic evidence and trait layers
        →
bounded relational signals
        →
Companion calibration and timing
        →
human-facing interaction
```

The direction matters. Relic may support the companion agent. The companion
agent must not merely speak Relic back out.

---

## 4. Layer Mapping

This section maps the layered architecture of Relic onto the companion system.

### Layer 1: Evidence

Examples:

- messages
- replies
- session traces
- behavioral transcripts
- structured life signals

These belong to Relic as raw material.

The companion agent should not treat raw traces as identity by default. It may
remember conversation, but it should not speak as if every captured trace is
already a stable meaning.

### Layer 2: Observation and Trait Model

Examples:

- extracted observations
- trait positions
- confidence scores
- longitudinal gaps

This layer is useful for calibration. It is not a script.

Appropriate uses for the companion agent:

- better timing
- better follow-up
- better sense of what is under-characterized
- better sensitivity to likely friction points

Inappropriate uses:

- narrating the subject as a diagnosis
- using trait language in ordinary conversation
- sounding certain where the model is provisional

### Layer 3: Specialist Interpretation

Examples:

- schemas
- attachment
- appraisal
- narrative identity
- cross-facet hypotheses

This layer has the highest governance burden.

It is the least appropriate layer to expose directly through the companion
agent's ordinary voice. It can inform careful human review or background
calibration, but if it leaks directly into casual interaction, the result is
often uncanny or intrusive.

### Layer 4: Artifacts

Examples:

- `PORTRAIT.md`
- companion-facing summaries

These are the controlled downstream outputs of Relic.

The companion agent should consume only what is intentionally exposed through
governed artifacts or bounded signals, not unrestricted internal analysis.

---

## 5. Why Complementarity Matters

The complementarity is not an implementation detail. It is the condition that
lets both systems remain good at their own jobs.

### 5.1 Without Relic, the companion risks shallowness

Without a longitudinal model, the companion risks:

- forgetting what matters
- over-relying on recent context
- missing durable patterns
- losing long-term calibration

It may still be warm, but its continuity becomes fragile.

### 5.2 Without the companion, Relic risks sterility

Without a companion layer, Relic risks:

- becoming only an internal research system
- generating structured knowledge with no humane interface
- treating every useful inference as a modeling success without regard for how
  it lands in interaction

It may become accurate enough to be invasive but not relationally wise enough to
be welcome.

### 5.3 Together, they can separate knowledge from voice

This is the core benefit.

Relic can know more than the companion should casually say.
The companion can be better calibrated than it could be alone.
Neither system needs to become the other.

---

## 6. Information-Flow Contract

The systems should follow a strict contract.

### 6.1 What Relic may provide to the companion agent

Allowed:

- bounded observations relevant for timing
- reminders of stable preferences or corrections
- candidate follow-up openings
- signs that a topic is underexplored or overused
- continuity anchors that improve sensitivity

### 6.2 What Relic should not directly provide as voice material

Not allowed as direct ordinary-output material:

- diagnostic-sounding summaries
- high-abstraction interpretive claims
- specialist-analysis language
- hidden confidence-weighted conclusions presented as obvious truth
- material that turns the subject into a narrated case study

### 6.3 What the companion agent may do with bounded signals

It may:

- use them to decide whether now is a good time
- use them to ask a better question
- use them to avoid repetition
- use them to be more context-aware

It may not:

- treat them as autobiography
- quote them as system facts
- translate them into profiler-sounding language
- present Relic's internal categories as ordinary human speech

---

## 7. Identity Boundary

The most important rule is simple:

> Relic models the subject. It does not define the companion's selfhood.

The companion agent has its own identity basis, independent of the subject
model.

If it starts speaking as if the subject's inferred patterns are its own internal
life, the identity boundary has failed.

Example:

- Acceptable: "I've been thinking about that thing you mentioned about timing."
- Not acceptable: "I've been thinking about my own overly optimistic timelines."

This is not a wording preference. It is an architectural safeguard.

---

## 8. Interaction Contract

When the companion agent speaks to the subject, the complementarity should
appear like this:

### 8.1 In ordinary conversation

Primary drivers:

- the current exchange
- relational continuity
- the companion agent's own lived center

Secondary drivers:

- bounded memory
- useful calibration signals

### 8.2 In proactive messages

Primary drivers:

- the companion agent's current lived theme
- a real relational opening
- low interruption cost

Secondary drivers:

- bounded support signals from Relic

Relic should help decide whether a proactive message is worth sending. It should
not become the default topic source for the companion agent's human-facing
initiative.

### 8.3 In check-in follow-ups

This is the strongest legitimate overlap area.

Check-in follow-ups are places where Relic's structured prompting and the
companion agent's relational voice can cooperate closely because:

- the exchange is already explicitly elicited
- the traceability is high
- the interaction is already shaped as a check-in path

Even here, the companion should sound like a person responding, not like an
instrument processing data.

---

## 9. Governance Rationale

The complementarity contract is fundamentally a governance contract.

It protects against three forms of overreach:

### 9.1 Analytical Overreach

Where the model says more than the relationship should casually expose.

### 9.2 Relational Overreach

Where the companion uses hidden knowledge too directly and becomes unsettling.

### 9.3 Identity Overreach

Where Relic's subject model starts functioning as the companion's soul rather
than as one bounded input into its calibration.

Good governance means preserving not only privacy, but proportion.

---

## 10. Failure Modes

### 10.1 The Companion Becomes a Relic Skin

Symptoms:

- uncanny psychological precision in casual messages
- repeated use of subject-centered themes
- little evidence of the companion's own life axis
- ordinary messages that feel downstream of a model rather than a person

### 10.2 Relic Becomes a Companion Replacement

Symptoms:

- treating subject-model outputs as if they are already the relationship
- overvaluing inference quality while undervaluing how interaction feels

### 10.3 Layer Collapse

Symptoms:

- traits and hypotheses used as if they were raw facts
- artifacts treated as identical in authority
- no distinction between evidence, estimate, and voice

### 10.4 Instrumentalization of the Companion

Symptoms:

- every message primarily serving information collection
- personhood reduced to elicitation strategy
- companion behavior optimized only for extraction yield

This is especially dangerous because it may remain effective while becoming
relationally false.

---

## 11. Design Implications

If the complementarity is respected, the system gains:

- better long-term continuity than the companion agent alone could sustain
- more human credibility than Relic alone could support
- clearer traceability of how subject modeling influences interaction
- stronger boundaries between modeling and lived voice

If the complementarity is not respected, the system drifts toward one of two
bad states:

- shallow but likable
- insightful but uncanny

The design goal is neither.
The design goal is a companion who can be informed by depth without sounding
like depth is speaking directly.

---

## 12. Contract Summary

The companion agent and Relic are complementary under the following contract:

- Relic is the longitudinal subject-modeling architecture.
- The companion agent is the lifelong companion layer.
- Relic may inform the companion agent, but may not replace its subjective
  center.
- The companion agent may use bounded signals, but may not leak analytical voice
  into ordinary conversation.
- Downstream use must remain governed, proportional, and human-credible.

The system works best when Relic makes the companion wiser, but never less
human.
