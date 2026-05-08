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
  <a href="#what-is-it">What is it?</a> ·
  <a href="#relic-and-gumi">Relic and Gumi</a> ·
  <a href="#status">Status</a> ·
  <a href="#quick-start">Quick Start</a> ·
  <a href="#profile-cli">Profile CLI</a> ·
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

This repository is in early OSS alpha. The implemented command surface is
smaller than the full research blueprint.

Implemented now:

- Python package and `python -m relic` smoke command
- `relic init` guided runtime setup (Ollama + Hermes); `relic subject create` for subject onboarding
- `relic setup` runtime installation/checks
- `relic subject create` guided subject/Gumi onboarding
- `relic profile` registry commands
- Gumi background generation, media canon generation, Hermes profile provisioning,
  Telegram delivery configuration, first-contact dry-run/live gates, and
  subject-specific Hermes cron specs
- deterministic privacy, correction, context, evaluation, and documentation tests
- local fixtures and CI helper scripts
- Researcher UI test skeleton under `ui/`

Planned or blueprint-backed, but not exposed as current CLI commands:

- full Hermes hook provisioning
- one-command Researcher UI launch
- fully guided live Hermes/Ollama/Telegram provisioning inside the setup TUI

Internal development notes, task packets, generated reports, and local
research outputs belong in `dev_docs/`. That directory is intentionally ignored
by git and is not part of the public OSS surface.

## Quick Start

This is the first-run path for someone who has just found the repository.
You do not need to know what Hermes is before starting. Relic setup checks the
local runtime, explains what is missing, and then opens the guided subject
bootstrap.

### 1. Install Locally

Requirements:

- Python 3.10+
- `pip`
- Node.js only if you are working on the optional `ui/` package
- Hermes only if you are developing the optional integration path

Core tests do not require cloud providers or a Hermes installation.

```bash
git clone https://github.com/yuzushi-dev/Relic
cd Relic
pip install -e .
relic init
```

`relic init` installs and configures the runtime tools (Ollama and Hermes).
Once done, run `relic subject create` to create your first subject and start
experimenting.

For development installs you can also run `python -m relic setup --bootstrap`
to create a local `.venv/` first, then activate it and run `relic init`.

### 2. Runtime Setup

If Relic is already installed in an active environment, run setup directly:

```bash
relic setup
```

The setup command checks whether Hermes and Ollama are available, explains that
they are optional for local dry-runs and required later for a live Gumi runtime,
and optionally configures them. It does not create a subject.

For a non-interactive check:

```bash
relic setup --check-only
```

### 3. Optional: Keep First-Run Data Inside the Repo

By default, profile data is written under `~/.relic`. For a first local trial,
you can keep all generated profile files inside the cloned repo:

```bash
export RELIC_HOME="$PWD/.relic-local"
```

`.relic-local/` is ignored by git. It is suitable for synthetic demo profiles,
not for committing real subject data.

Relic also prepares one private Hermes/Gumi profile per subject. By default,
those profile directories are created under `~/.hermes/profiles/`. For an
isolated first run, keep them inside the repo too:

```bash
export HERMES_PROFILES_HOME="$PWD/.relic-local/hermes-profiles"
```

Then run:

```bash
relic subject create
```

### 4. Create the First Subject

After `relic init` completes, create your first subject:

```bash
relic subject create
```

The guided subject flow creates two linked private profiles:

- a Relic subject profile under `$RELIC_HOME/subjects/subj_001/`
- a subject-specific Hermes/Gumi profile named `gumi-subj_001`

The important fields on a fresh profile are:

```json
{
  "subject_id": "subj_001",
  "experiment_id": "exp_001",
  "status": "draft",
  "hermes_profile_name": "gumi-subj_001",
  "profile_version": 1
}
```

Relic also creates the local profile directory:

```text
$RELIC_HOME/subjects/subj_001/
  subject_profile.json
  provenance/
  exports/
```

And it prepares the private Gumi profile directory:

```text
$HERMES_PROFILES_HOME/gumi-subj_001/
  SOUL.md
  USER.md
  MEMORY.md
```

At this stage, `SOUL.md`, `USER.md`, and `MEMORY.md` are safe initial
placeholders for the subject-specific Gumi profile. Depending on choices in the
TUI, Relic may also generate the Gumi background, provision the private Hermes
profile, and compose a local first-contact preview. It does not start a live
runtime or send a live message unless live delivery is explicitly configured.

### 5. Make Gumi Live

Dry-run setup does not require Hermes, Ollama, Telegram, cloud credentials, or a
running gateway. To make a subject-specific Gumi live, use the TUI/check output
as the guide:

- Install Ollama from https://ollama.com/download if it is missing.
- Use `ollama signin` if you want to start with Ollama cloud models instead of
  relying on local hardware.
- Install Hermes if it is missing.
- Configure Hermes to use Ollama's OpenAI-compatible local endpoint
  `http://localhost:11434/v1`.
- Create a dedicated Telegram bot and dedicated Telegram user/chat id for each
  subject.
- Configure that subject with `relic profile hermes configure-telegram`.
- Provision subject-specific cron with `relic profile hermes cron provision`.

The lower-level commands remain available for scripted runs:

```bash
relic profile edit subj_001 --status baseline_in_progress
relic profile edit subj_001 --status baseline_complete
relic profile gumi generate subj_001 --mode hybrid --seed 42
relic profile edit subj_001 --status gumi_seed_reviewed
relic profile hermes provision subj_001
relic profile hermes show subj_001
relic profile gumi media generate subj_001 --seed 42
relic profile gumi intro compose subj_001 --seed 7
relic profile gumi intro send subj_001 --dry-run
```

`--dry-run` records the local send event and never contacts a live delivery
provider. `--deliver` prepares Hermes-native Telegram delivery. Actual send
requires `--live` and `RELIC_ALLOW_LIVE_DELIVERY=1`.

The generation step writes subject-local artifacts:

```text
$RELIC_HOME/subjects/subj_001/
  gumi_background_profile.json
  gumi_seed_profile.json
  gumi_sweet_spot_config.json
  gumi_world.md
  gumi_relationship_policy.md
  gumi_social_graph.json
  gumi_visual_canon.json
  gumi_music_canon.json
  gumi_daily_rhythm.json
  provenance/gumi_generation_report.json
```

The provisioning step writes the private Hermes profile:

```text
$HERMES_PROFILES_HOME/gumi-subj_001/
  SOUL.md
  USER.md
  MEMORY.md
  config.yaml
  .env
  workspace/gumi/background.json
  workspace/gumi/world.md
  workspace/gumi/relationship_policy.md
  workspace/gumi/visual_canon.json
  workspace/gumi/voice_canon.json
  workspace/gumi/lyria_canon.json
  workspace/gumi/media_policy.json
```

### 6. Run the Public Checks

```bash
make lint
make test
python scripts/ci/check_json_jsonl.py
python scripts/ci/check_no_raw_private_data.py
```

These checks exercise the current OSS surface. They do not require real private
data, a running agent, cloud credentials, or Hermes.

## Profile CLI

Relic installation creates the system capability. `relic profile init` then
creates a Relic subject profile and prepares that subject's private Hermes/Gumi
profile shell. The nested `gumi` and `hermes` commands generate and provision
the subject-specific Gumi profile. None of these commands start Hermes or
contact the subject.

Current profile commands:

```text
list
show
init
edit
validate
export
archive
gumi generate <subject_id> --mode random|manual|hybrid
gumi media generate <subject_id>
gumi media show <subject_id>
gumi intro compose <subject_id>
gumi intro send <subject_id> --dry-run|--deliver [--live]
hermes provision <subject_id>
hermes show <subject_id>
hermes configure-telegram <subject_id>
hermes cron provision <subject_id>
hermes cron list <subject_id>
hermes cron validate <subject_id>
```

Create and inspect a local subject profile:

```bash
relic profile init --subject-id subj_001 --experiment-id exp_001
relic profile list
relic profile show subj_001
relic profile validate subj_001
```

Edit, export, and archive:

```bash
relic profile edit subj_001 --status baseline_in_progress
relic profile edit subj_001 --status baseline_complete
relic profile gumi generate subj_001 --mode random --seed 42
relic profile edit subj_001 --status gumi_seed_reviewed
relic profile hermes provision subj_001
relic profile gumi media generate subj_001 --seed 42
relic profile gumi intro compose subj_001
relic profile gumi intro send subj_001 --dry-run
relic profile export subj_001 --redacted --out profile.json
relic profile archive subj_001
```

The guided subject command runs the local subject/Gumi generation path:

```bash
relic subject create
```

A single researcher can manage multiple subjects. Each subject has a separate
Relic profile and a separate private Hermes/Gumi profile. Live Telegram setup
requires a dedicated bot token and dedicated Telegram user/chat id per subject;
Relic rejects reused Telegram identifiers across subjects.

## Development Checks

The Makefile is the main command registry:

```bash
make lint
make test
make test-docs
make test-privacy
make test-eval
make test-ui
```

Additional deterministic checks:

```bash
python scripts/ci/check_json_jsonl.py
python scripts/ci/check_no_raw_private_data.py
python scripts/validate_handoff.py
```

Build packaging artifacts with:

```bash
python -m build --sdist --wheel
```

If that command fails with `No module named build`, install the standard build
frontend first:

```bash
pip install build
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
