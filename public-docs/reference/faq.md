# FAQ

Short answers to the questions researchers ask most often. Pointers to deeper reading where it matters.

## What does Relic actually do?

It maintains an inspectable, correctable model of one subject over many conversations, and runs a companion agent (Gumi) that uses that model under governance rules. See [Getting Started](../guides/getting-started.md) for the long version.

## Is Relic a clinical tool?

No. Relic does not diagnose, screen, or rate mental health. Facets are theoretical modeling dimensions with confidence scores, not psychometric verdicts. See [No Clinicalization](../ethics/no-clinicalization.md).

## Do I need to know how to code?

No. The CLI and the workbench cover normal research workflows. Coding is needed only for developing new modules or contributing to the project — see [Contributing](../contributing/index.md).

## Do I need a GPU?

No. Ollama runs on CPU. A GPU makes the local model faster, but it is not required.

## What hardware should I plan for?

- CPU-only: 16 GB RAM minimum, models like `llama3.2:3b` work but quality is modest.
- With GPU (or 32 GB+ RAM): the default `qwen2.5:32b-instruct-q4_K_M` is comfortable.

See [Installation](../guides/installation.md).

## Does Relic send my data anywhere?

By default, no. Inference runs on local Ollama. The database is local. Only if you configure Telegram delivery or a hosted memory provider does data leave the machine, and only by those explicit channels.

## Can I use real participant data?

Only with explicit informed consent and a deployment that meets the constraints in [Ethics](../ethics/index.md). The architecture supports it; the responsibility is yours.

## Is Gumi a chatbot I can talk to as the researcher?

No. Each Gumi instance is scoped to one subject. There is no researcher-facing Gumi. The researcher interacts with **the model** and **the system**, not the agent. See [Researcher Boundary](../concepts/researcher-boundary.md).

## What is the difference between Relic and Gumi?

Relic is the governance and modeling layer. Gumi is the diegetic agent the subject talks to. Relic decides what Gumi may remember, what may shape her behavior, and what stays researcher-only. See [Relic and Gumi](../concepts/relic-and-gumi.md).

## What happens if Gumi says something wrong about the subject?

Submit a correction from the workbench. Corrections are first-class: they are recorded, propagate through the compiler pipeline, and invalidate stale artifacts. See [Corrections and Replay](../guides/corrections-and-replay.md).

## How do I get a Telegram bot token?

Talk to `@BotFather` on Telegram, send `/newbot`, follow the prompts. Full walkthrough: [API Keys and Tokens](../guides/api-keys-and-tokens.md).

## How do I find a subject's Telegram user ID?

Ask them to message `@userinfobot`; it replies with their numeric ID.

## Where does my data live?

- Subject data and audit trail: `~/.relic/relic.db` (SQLite).
- Gumi's identity files and credentials: `$HERMES_HOME/<profile>/` (default `~/.hermes/`).
- Generated media and exports: wherever you point the export commands.

## Can a subject delete their data?

Yes. Three levels: pause (suspend proactivity), forget (remove from recall, keep audit), delete (full erase, GDPR Art. 17). See [Export and Deletion](../guides/export-and-deletion.md).

## What is a confidence score?

A number from 0.0 to 1.0 attached to every facet estimate, indicating how much evidence supports it. A trait with 0.2 confidence is a hypothesis; one with 0.85 has accumulated enough signal to be treated as established within this domain. Confidence is never absolute and never clinical.

## Why does Relic refuse to show me the raw safety signal in an export?

Safety signals are researcher-facing governance objects. They are not shown to the subject, not stored in Gumi's memory, and not included in subject-facing exports. See [Behavioral Boundaries](../ethics/boundaries.md).

## I made a mistake during bootstrap. Do I have to start over?

No. Re-run `relic subject create` with the same `--subject-id`. The wizard resumes from the last completed step. To inspect a checkpoint: `relic-profile bootstrap resume <session_id>`.

## How do I cite Relic in a paper?

See [Citing Relic](../research/citing-relic.md). `CITATION.cff` at the repo root has the structured citation.

## Where is the source code?

[github.com/yuzushi-dev/Relic](https://github.com/yuzushi-dev/Relic). License is AGPL-3.0.
