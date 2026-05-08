<p align="center">
  <img src="https://readme-typing-svg.herokuapp.com?font=JetBrains+Mono&weight=800&size=42&duration=3000&pause=1000&color=3A86FF&center=true&vCenter=true&width=700&lines=RELIC" alt="Relic">
</p>

<p align="center">
  <em>Longitudinal Relational Modeling for Reflective Agents</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/language-Python-blue?style=for-the-badge&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/focus-Longitudinal%20Modeling-purple?style=for-the-badge" alt="Longitudinal Modeling">
  <img src="https://img.shields.io/badge/status-OSS%20Alpha-orange?style=for-the-badge" alt="OSS Alpha">
  <img src="https://img.shields.io/badge/license-AGPL--v3-red?style=for-the-badge" alt="AGPL-3.0">
</p>

<p align="center">
  <a href="#what-is">What is it?</a> ·
  <a href="#relic-and-gumi">Relic and Gumi</a> ·
  <a href="#status">Status</a> ·
  <a href="#quick-start">Quick Start</a> ·
  <a href="#commands">Commands</a> ·
  <a href="#architecture">Architecture</a> ·
  <a href="#safety-boundaries-and-ethics">Ethics</a> ·
  <a href="#lore">Lore</a>
</p>

---
> *Relic preserves continuity. It preserves memory. It does not claim to be the person. What runs afterward is a model with context, not a replacement for a life.*
>
> *Gumi is where that continuity becomes a relationship: a diegetic agent with its own world, voice, and history, while Relic quietly governs how the user’s lived experience is remembered, corrected, and carried forward.*

---

## What Is It?

Relic is a runtime governance and longitudinal modeling layer for reflective
agents. It is designed to capture behavioral signals from conversational
interaction, maintain evolving subject profiles, and produce inspectable runtime
context under privacy, correction, and provenance constraints.

Relic models interaction across theory-derived behavioral and personality
facets. These facets are not clinical scales, diagnoses, or claims of
psychometric certainty. They are inspectable modeling dimensions for
longitudinal observation, hypothesis generation, correction, and runtime
governance.

Unlike a static character card or a prompt template, a Relic profile is not a
fixed description written once and reused forever. It can start from structured
bootstrap data and then evolve through passive interaction, active elicitation,
explicit correction, governed inference, and review.

Relic does not rely only on questionnaire-style self-report. It combines
baseline initialization, longitudinal interaction data, confidence tracking,
provenance, and correction mechanisms. The system explicitly represents the
limits of what it knows.

## Theoretical Grounding

The facet model is derived from established frameworks in cognitive and
personality psychology:

- **Cognitive Appraisal Theory**: appraisal patterns and stress-response facets
- **Self-Determination Theory**: autonomy, competence, and relatedness dimensions
- **Attachment Theory**: relational style and help-seeking facets
- **Dual-Process Theory**: System 1 / System 2 behavioral signatures
- **CAPS**: situation-behavior signature modeling
- **LIWC**: linguistic behavioral markers

Each facet is represented as a continuous position on a theory-grounded bipolar
spectrum, not a categorical label. Every trait carries a confidence score and an
observation count; confidence scores range from 0.0 to 1.0. Nascent facets
typically start with sparse evidence and should be treated as tentative.

Relic does not claim that these facets are clinical scales or psychometric
diagnoses. They are modeling dimensions for longitudinal inspection, hypothesis
generation, and governed runtime adaptation.

## Relic and Gumi

Relic is the governance and modeling layer. Gumi is the diegetic relational agent generated for a specific subject profile.

A Gumi instance is not a copy of the subject and is not a transparent interface to Relic. She has her own background, voice, routines, world, boundaries, relationships, aesthetic continuity, and expressive style. Relic initializes and governs the conditions that make this continuity possible, while keeping user evidence, active elicitation, Gumi’s diegetic events, generated expressive acts, and runtime personalization separated in the data model.

The goal is not to make Gumi identical to the subject, nor to make her arbitrarily different. The bootstrap process searches for a calibrated relational distance: enough similarity to make interaction feel legible and continuous, enough difference to preserve Gumi’s agency, perspective, surprise, and boundaries.

Gumi can take initiative inside the relationship: proactive messages, expressive media, audio, images, music, diegetic life fragments, and continuity events. These acts are part of the user’s lived experience with Gumi, but they are not passive observations about the user. They can shape the relationship, and the user’s responses to them can become eligible data, but Gumi’s own diegetic events do not update the user model by themselves.

## Status

OSS alpha. Core surface: `relic init`, `relic subject create`, `relic setup`.

Implemented: Python package, guided runtime setup, subject/Gumi bootstrap, profile management, Gumi generation, Hermes provisioning, Telegram delivery gates, cron specs, privacy/correction/context tests, CI scripts.

Planned: full Hermes hook provisioning, one-command Researcher UI launch.

## Quick Start

Requirements: Python 3.10+, `pip`. Optional: Hermes for live delivery.

```bash
git clone https://github.com/yuzushi-dev/Relic
cd Relic
pip install -e .
relic init
relic subject create
```

`relic init` installs and configures Ollama and Hermes. `relic subject create` creates first subject and starts guided Gumi bootstrap.

For isolated first run, keep all data inside the repo:

```bash
export RELIC_HOME="$PWD/.relic-local"
export HERMES_PROFILES_HOME="$PWD/.relic-local/hermes-profiles"
relic init
relic subject create
```

## Commands

### `relic init`

First-run wizard. Installs and configures Ollama and Hermes. Run once before creating subjects.

### `relic subject create`

Guided bootstrap for new subject. Creates Relic subject profile and Gumi diegetic profile. No live delivery until explicitly configured.

### `relic setup`

Install/check runtime dependencies without creating subjects. Use `--check-only` for non-interactive check.

## Development Checks

Run the full test suite and static checks:

```bash
make lint
make test
python scripts/ci/check_json_jsonl.py
python scripts/ci/check_no_raw_private_data.py
```

## Architecture

```text
Researcher-mediated bootstrap
       |
       +---> Subject profile
       +---> Gumi diegetic profile
       +---> Runtime context artifacts
       |
Interaction stream
       |
       +---> Passive capture
       +---> Active elicitation decisions
       +---> Gumi diegetic / expressive events
       |
Relic ingestion
       |
       +---> Observations
       +---> Signals
       +---> Traits / hypotheses
       +---> Corrections / review
       |
Runtime governance
       |
       +---> Profile sync
       +---> Policy gates
       +---> Governed context
```

Relic keeps these concepts separate:

- subject profile data
- evidence and source references
- traits, hypotheses, and confidence
- correction and review state
- generated runtime artifacts
- privacy traces and redaction checks
- research-only orchestration documents

At runtime, a profile should be treated as an inspectable, contestable model. A
generated artifact is valid only when it can be traced back to allowed evidence
and policy snapshots.

### Scheduled Jobs as Decision Points

```text
Cron tick
       |
       +---> Eligibility gate
       |         quiet hours · rate limit · opt-out · sensitivity · open loop
       |
       +---> Decision
       |         NO_REPLY · blocked · candidate · deliver
       |
       +---> Logged event
       |         decision point · source refs · policy snapshot · outcome
       |
       +---> Relic ingestion
                 only if eligible interaction data exists
```

A scheduled Gumi job is a decision point, not an automatic intervention.

## Design Principles

Every architectural decision reflects these constraints:

- **Theoretical grounding**: facets are derived from attachment theory, appraisal theory, self-determination theory, dual-process cognition, CAPS, and linguistic-behavioral analysis.
- **Epistemic humility**: every trait carries uncertainty. The system explicitly represents what it does not know.
- **Inspectability**: structured data, traceable decisions, reviewable outputs, and versioned profile changes.
- **Separation of streams**: passive interaction, active elicitation, Gumi diegetic events, expressive media, and user evidence are not collapsed into one data source.
- **Human readability**: outputs are written to be read and questioned by a person, not only parsed by machines.
- **Consent and separation**: demo data and real behavioral data are architecturally separated. Subject profiles are exportable, editable, and archivable.
- **Epistemic accountability**: inferred claims are subject to structured verification, correction, and audit.

## Safety, Boundaries, and Ethics

Relic operates in a sensitive problem space. **The ethics are not optional.**

- Use synthetic or explicitly consented data only.
- Do not deploy hidden monitoring or covert profiling.
- Do not treat model output as clinical, diagnostic, or forensic truth.
- Keep a hard separation between demo artifacts and real personal data.
- Prefer inspectable, reviewable outputs over opaque automation.
- Do not let Gumi's diegetic life events become evidence about the subject.
- Do not use generated media or first-person fragments to infer subject traits unless the user responds and the response is eligible for ingestion.
- Preserve boundaries against dependency escalation, exclusive attachment dynamics, and manipulative engagement loops.
- Support opt-out, archive, export, and correction workflows.
- Keep lab, runtime, and generated artifacts separated by explicit gates.

Private databases, live credentials, personal logs, raw behavioral data,
subject-specific local profiles, and real media artifacts are excluded from this
repo. Sensitive marker scans live under `tests/`, and public examples use
synthetic demo data only.

## Repository Hygiene

Public-facing source should stay in tracked package, test, fixture, script, and
UI paths. Local-only development material should stay under ignored directories
such as:

```text
dev_docs/
artifacts/
.claude/
.codex/
.agents/
skills/
.venv/
```

Before publishing, run:

```bash
git status --short
make lint
make test
python scripts/ci/check_json_jsonl.py
python scripts/ci/check_no_raw_private_data.py
```

## License

[AGPL-3.0](LICENSE.txt): if you use this in a product or network service, your
modifications must be open source too.

---

## Lore

The name comes from *Cyberpunk 2077*. **Relic** is a Black Program originally
developed to map the human psyche into a structured digital form: and weaponized
to create Mikoshi, a data fortress of captured minds with no exit. The
philosophical problem the game surfaces is whether a perfect copy of a person
*is* that person, and who controls the copy. This framework deliberately
inhabits that tension.

Relic draws from the same conceptual space: personality as structured,
observable, persistent data. The difference is consent, inspectability,
correction, and the knowledge that the model is not the person.

Gumi sits on the other side of the same problem. She is not the subject and not
a transparent system prompt. She is a relational presence with a diegetic life,
governed by Relic but not reduced to it in the user experience.

> *"What runs afterward is not you. It is data that remembers being you."*

<p align="center">
  <em>Longitudinal Relational Modeling for Reflective Agents</em>
</p>
