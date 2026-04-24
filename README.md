<p align="center">
  <img src="https://readme-typing-svg.herokuapp.com?font=JetBrains+Mono&weight=800&size=42&duration=3000&pause=1000&color=3A86FF&center=true&vCenter=true&width=700&lines=RELIC" alt="Relic">
</p>

<p align="center">
  <em>Longitudinal Personality Modeling for Reflective Agents</em>
</p>

<p align="center">
  <a href="https://yuzushi-dev.github.io/Relic/" target="_blank" rel="noopener noreferrer">Relic live demo</a>
</p>

<p align="center">
  <img src="docs/sk_demo-2x.png" alt="Relic demo UI" width="430">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/language-Python-blue?style=for-the-badge&logo=python" />
  <img src="https://img.shields.io/badge/focus-Cognitive%20Modeling-purple?style=for-the-badge" />
  <img src="https://img.shields.io/badge/interface-UX%20First-pink?style=for-the-badge" />
  <img src="https://img.shields.io/badge/license-AGPL--v3-red?style=for-the-badge" />
</p>

<p align="center">
  <a href="#what-is-it">What is it?</a> ·
  <a href="#theoretical-grounding">Theoretical Grounding</a> ·
  <a href="#architecture">Architecture</a> ·
  <a href="#quick-start">Quick Start</a> ·
  <a href="#safety-and-ethics">Ethics</a> ·
  <a href="#lore">Lore</a>
</p>

---

> *Relic preserves continuity. It preserves memory. It does not claim to be the person.*
> *What runs afterward is a model with context, not a replacement for a life.*

---

## What Is It?

Relic is a framework for longitudinal behavioral modeling of individual subjects, organized around a single research question:

> Can an AI system build a deep, structured model of how a person thinks and behaves over time — remaining inspectable, theoretically grounded, and continuously updated — without requiring clinical access or invasive instrumentation?

The system accumulates behavioral signal across five stages:

1. **Capture** — messages, sessions, biofeedback, voice notes
2. **Extract** — LLM-driven analysis into 60 structured personality facets
3. **Accumulate** — weighted observations with confidence scores and temporal decay
4. **Synthesize** — trait positions, cross-facet hypotheses, narrative portrait
5. **Expose** — PORTRAIT.md injected into agent sessions at bootstrap

The output is not a score. It is a continuously deepening behavioral portrait grounded in psychological theory.

---

## Theoretical Grounding

The 60-facet model is derived from established frameworks in cognitive and personality psychology:

- **Cognitive Appraisal Theory** (Lazarus & Folkman) — appraisal patterns and stress-response facets
- **Self-Determination Theory** (Deci & Ryan) — autonomy, competence, and relatedness dimensions
- **Attachment Theory** (Bowlby / Ainsworth) — relational style and help-seeking facets
- **Dual-Process Theory** (Kahneman) — System 1 / System 2 behavioral signatures
- **CAPS** (Mischel & Shoda) — situation-behavior signature modeling
- **LIWC** (Pennebaker et al.) — linguistic behavioral markers

Each facet is represented as a continuous position on a theory-grounded bipolar spectrum, not a categorical label. Every trait carries a confidence score and an observation count; the system explicitly represents the limits of its own knowledge.

---

## Architecture

```
Behavioral signal
       |
       +---> [Hook: relic-capture]
       |         Captures inbound messages -> inbox
       |         Detects check-in replies -> triggers follow-up
       |
       +---> [Hook: relic-bootstrap]
       |         Injects PORTRAIT.md into every agent session
       |         All agents respond with personality awareness
       |
       +---> [Cron: relic:extract]         every 2h
       |         Ingests inbox -> LLM extracts personality signals
       |         Inserts observations into SQLite
       |
       +---> [Cron: relic:checkin]          every 30min
       |         Scores 60 facets -> selects highest gap facet
       |         Generates natural question -> delivers via Telegram
       |
       +---> [Cron: relic:passive-scan]     every 6h
       |         Scans relational-agent session transcripts
       |         Extracts behavioral meta-signals
       |
       +---> [Cron: relic:synthesize]       daily 03:00
       |         Consolidates observations -> trait scores + confidence
       |         Generates cross-facet hypotheses via LLM
       |
       +---> [Cron: relic:profile-sync]     daily 03:30
       |         Syncs to subject_profile.json
       |         Generates human-readable PORTRAIT.md
       |
       +---> [Daily enrichment]                  04:00-05:00
       |         entity-extract · decisions · healthcheck · memory
       |         biofeedback-pull · biofeedback-gadgetbridge · muse-aggregate
       |
       +---> [Weekly analysis]                   Sunday / Monday
       |         liwc · stress-index
       |
       +---> [Monthly specialist analyzers]      1st-5th of each month
                 schemas · goals · sdt · portrait · idiolect
                 caps · attachment · defenses · narrative
                 appraisal · mental-models · dual-process · constructs
```

### The 60-Facet Model

Personality is modeled across 60 facets in 8 categories, each as a continuous position on a theory-grounded bipolar spectrum:

| Category | Facets | Example spectrum |
|---|---|---|
| Cognitive | 6 | impulsive ↔ deliberate |
| Emotional | 8 | reactive ↔ regulated |
| Communication | 6 | terse ↔ expansive |
| Relational | 9 | avoidant ↔ secure |
| Values | 7 | self-oriented ↔ other-oriented |
| Temporal | 6 | reactive ↔ anticipatory |
| Metabolic / Lifestyle | 10 | degraded ↔ optimal |
| Meta-Cognition | 7 | opaque ↔ reflective |

Each facet carries a position `[0.0 - 1.0]`, a confidence score, and an observation count. The model expands with each version; see the whitepaper for the current full taxonomy.

---

## Project Stats

```
language       Python 3.12+
modules        60+ extracted source files
facets         60 personality dimensions
categories     8 (cognitive · emotional · communication · relational ·
                  values · temporal · metabolic · meta-cognition)
integrations   Telegram · Zepp/Amazfit · Actual Budget · Muse 2 EEG · voice
hooks          2   (relic-capture · relic-bootstrap)
crons          36  (6 core · 4 daily · 5 biofeedback · 2 weekly · 5 optional · 13 monthly specialist)
tests          189 (sanitization · packaging · demo · repo-readiness · unit)
public entry   synthetic demo flow
license        AGPL-3.0
```

---

## Quick Start

Requirements: **Python 3.12+**, **OpenClaw 31.3.26**

Public branding note: prefer the `relic-*` commands and `python -m relic.*`.
No `soulkiller-*` entrypoints were preserved. Migrate directly to the `relic-*` commands listed below.

### Run the demo (no OpenClaw required)

```bash
git clone https://github.com/yuzushi-dev/relic
cd relic
pip install -e .

relic-demo --output-dir demo/generated
relic-demo-ui --output-dir demo/generated
open demo/generated/demo_console.html
```

Demo outputs:

```
demo/generated/
├── model_profile.md           <- structured facet snapshot
├── model_portrait.md          <- narrative behavioral portrait
├── summary.json               <- machine-readable summary
├── event_log.sample.jsonl     <- synthetic captured events
├── demo_console.html          <- static monitoring interface
└── relic.db                   <- SQLite database for the live monitoring UI
```

### Run the live monitoring UI

The webui reads from `relic.db`. The demo runner writes one automatically, so you can spin up the UI without a live OpenClaw installation:

```bash
pip install -e ".[webui]"

relic-demo --output-dir demo/generated
RELIC_DATA_DIR=demo/generated OPENCLAW_HOME=demo/generated python -m relic.webui --port 8765
```

Open `http://localhost:8765` to see the dashboard populated with synthetic demo data.

For a live installation (requires an active pipeline with at least one extraction cycle completed):

```bash
# if installed via wizard (.env is already written):
source .env && python -m relic.webui --port 8765

# or manually:
RELIC_DATA_DIR=~/.relic/<subject-id> python -m relic.webui --port 8765
```

---

### Connect to your OpenClaw instance

```bash
python install.py
```

The installation wizard will walk you through subject configuration, hook registration, and cron setup. Run `python install.py --dry-run` to preview without writing anything.

**LLM provider** — the extraction pipeline requires a model. The easiest path is [Ollama](https://ollama.com) (local, no API key):

```bash
ollama pull llama3
```
```env
RELIC_MODEL=llama3
RELIC_PROVIDER=ollama
```

Anthropic and OpenAI are also supported. See [docs/ADAPTERS.md](docs/ADAPTERS.md).

The wizard configures:

- Subject identity and runtime data directory
- OpenClaw hooks: relic-capture · relic-bootstrap
- 36 cron jobs across core pipeline, daily enrichment, biofeedback, weekly analysis, and monthly specialist analyzers
- Environment file (`.env`) with your full configuration

---

## Rename Notice

This project was previously published as **Soulkiller** and is being renamed to **Relic**.

The rename may be a **breaking change** for existing installations and automation. Check imports, CLI commands, cron IDs, environment variables, hook names, data directories, and documentation links before upgrading. No compatibility shims were preserved. New integrations must use the `relic` package namespace, `relic-*` CLI commands, and `RELIC_*` environment variables.

---

## What the Repo Includes

| Path | Contents |
|---|---|
| `src/relic/` | Core Python modules + public demo utilities |
| `src/lib/` | Runtime shims (log, config, OpenClaw client stubs) |
| `hooks/` | OpenClaw integration hooks (TypeScript) |
| `docs/` | Architecture, whitepaper, design documents, runtime contract |
| `demo/` | Synthetic fixtures and expected outputs |
| `tests/` | Sanitization, packaging, demo, and repo-readiness tests |

**Documentation:**

| Doc | What it covers |
|---|---|
| [INSTALL.md](INSTALL.md) | Prerequisites, wizard, manual setup, backfill |
| [docs/CONFIGURATION.md](docs/CONFIGURATION.md) | Every env var with examples and directory layout |
| [docs/ADAPTERS.md](docs/ADAPTERS.md) | How to connect an LLM provider (Anthropic, OpenAI, Ollama, OpenClaw) |
| [docs/architecture/RELIC.md](docs/architecture/RELIC.md) | Full pipeline internals |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Dev setup, adding crons, sanitization rules, PR process |

---

## Reproducing the whitepaper figures

The §9 figures in `docs/whitepaper/CPIS_whitepaper.md` come from a private deployment and are not shipped in the repo. To regenerate equivalent metrics and figures from your own `relic.db`:

```bash
python3 scripts/reproduce_evaluation.py --db path/to/relic.db --out out/
# writes out/metrics.json and (if matplotlib is installed)
#   out/figure2_convergence.png
#   out/figure3_sources.png
```

`metrics.json` carries the headline numbers reported in the paper: coverage, average confidence, cumulative observations, source composition, schema state, hypothesis count. PNG rendering requires `matplotlib`.

---

## Design Principles

Every architectural decision reflects five constraints:

- **Theoretical grounding** — facets are derived from attachment theory, appraisal theory, SDT, dual-process cognition, and CAPS, not invented.
- **Epistemic humility** — every trait carries a confidence score. The system explicitly represents what it does not know.
- **Inspectability** — structured data, traceable decisions, outputs that can be read and questioned by the subject.
- **Human readability** — PORTRAIT.md is written to be read by a person, not parsed by a machine.
- **Consent and separation** — demo data and real behavioral data are architecturally separated. The subject controls the data.

---

## Safety and Ethics

Relic operates in a sensitive problem space. **The ethics are not optional.**

- Use **synthetic or explicitly consented data** only
- Do not deploy hidden monitoring or covert profiling of any kind
- Do not treat model output as clinical, diagnostic, or forensic truth
- Keep a hard separation between demo artifacts and any real personal data
- Prefer inspectable, reviewable outputs over opaque automation

Private databases, live credentials, personal logs, and raw behavioral data are **excluded** from this repo. Sensitive marker scans live under `tests/`, and public examples use synthetic demo data only.

---

## License

[AGPL-3.0](LICENSE) — if you use this in a product or service, your modifications must be open source too.

---

## Lore

The name comes from *Cyberpunk 2077*. **Relic** is a Black Program originally developed to map the human psyche into a structured digital form — and weaponized to create Mikoshi, a data fortress of captured minds with no exit. The philosophical problem the game surfaces — whether a perfect copy of a person *is* that person, and who controls the copy — is the tension this framework deliberately inhabits.

The framework draws from the same conceptual space: personality as structured, observable, persistent data. The difference is consent, transparency, and the knowledge that the model is not the person.

> *"What runs afterward is not you. It is data that remembers being you."*

<p align="center">
  <em>Longitudinal Personality Modeling for Reflective Agents</em>
</p>
