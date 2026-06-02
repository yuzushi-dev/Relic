# Getting Started

A five-minute orientation for researchers approaching Relic for the first time. No prior experience with the codebase is assumed; basic familiarity with a terminal is enough.

## What Relic does, in plain words

Relic is a research tool for studying how a conversational agent maintains a relationship with one person over time. It does two things:

1. It keeps an **inspectable, correctable model** of the subject: observations, traits, confidence scores, source references. Nothing is hidden; everything can be reviewed and corrected.
2. It runs a companion agent (**Gumi**) that uses that model under strict governance rules: what may be remembered, what may be said back, what stays researcher-only, what the subject can pause or delete.

Relic is **not** a clinical tool. It does not diagnose, screen, or rate mental health. Facets are theory-grounded modeling dimensions with confidence scores, not psychometric verdicts. See [No Clinicalization](../ethics/no-clinicalization.md).

## How the pieces fit together

```
+------------+    bootstrap    +--------------+   Hermes gateway   +-----------+
| Researcher | --------------> |    Relic     | -----------------> |   Gumi    |
|  (you)     |                 | (governance) |                    | (agent)   |
+------------+                 +------+-------+                    +-----+-----+
      ^                               |                                  |
      | inspect / correct             | reads & writes                   | chats
      |   (workbench)                 v                                  v
      |                       +----------------+                  +-------------+
      +---------------------- |   relic.db     |                  |   Subject   |
                              | (SQLite, local)|                  | (Telegram)  |
                              +----------------+                  +-------------+
```

You interact with **Relic** through the CLI and the workbench. The subject interacts with **Gumi** through their delivery channel (Telegram). The two never talk to the same surface.

## What you will work with

| Surface | What it is | When to use it |
|---|---|---|
| `relic` CLI | Terminal commands for setup, subjects, runtime ops | Setup, day-to-day admin |
| Researcher workbench | Local web UI for inspecting and correcting profiles | Review, correction, audit |
| Gumi (via Hermes) | The agent the subject actually talks to | Only the subject sees this |
| `relic.db` | Single local SQLite file with all subject data | Backed up like any file |

You will not write code to use Relic. The CLI and the workbench cover normal research workflows.

## What you need before starting

- A computer with at least 16 GB RAM (32 GB recommended if you want to run larger local models).
- Python 3.10 or newer. Linux or macOS native; **Windows requires [WSL2](https://learn.microsoft.com/en-us/windows/wsl/install)**.
- A Telegram account if you want to deliver messages over Telegram. See [API Keys and Tokens](api-keys-and-tokens.md).
- Disk: ~2 GB for Relic + ~20 GB for the default Ollama model (`qwen2.5:32b-instruct-q4_K_M`) or ~2 GB for the small fallback (`llama3.2:3b`).
- Time: ~30 min for the install steps **plus** the model download. A 20 GB pull on a typical home connection takes 30–60 min on top.

You do **not** need a GPU. Local models will run on CPU; they will be slower but functional.

## Budget cheat sheet

| Item | Default | Minimum |
|---|---|---|
| Disk | 22 GB | 4 GB (small model) |
| RAM | 24 GB free for the model | 8 GB (small model) |
| Network | 20 GB pull once | 2 GB (small model) |
| Money | $0 (all local) | $0 |

If you also enable Gemini for media, expect modest Google API usage within the free tier for light testing. See [API Keys and Tokens](api-keys-and-tokens.md).

## Want to look before installing?

The repo deploys a static workbench build to GitHub Pages: **[yuzushi-dev.github.io/Relic/](https://yuzushi-dev.github.io/Relic/)**.

It runs entirely in the browser against synthetic demo data. No backend, no install. Use it to evaluate the UI shape before committing time to the full install. The live demo cannot run real subjects, for that you need the local install below.

See also [Demo Quickstart](demo-quickstart.md) for two faster local paths: a synthetic eval pipeline and a pre-populated workbench DB.

## The path from zero

1. **Install**: [Installation](installation.md). `git clone`, `pip install -e .`, `relic init` wizard.
2. **Bootstrap a synthetic subject**: [First Subject](first-subject.md). Use the wizard to create a demo profile with synthetic data. Nothing is sent to anyone.
3. **Open the workbench**: `relic ui`, then visit `http://localhost:8080`. Look at the generated profile, the timeline, the CAC traces.
4. **Wire up Telegram and start Gumi**: only when you are ready to talk to a real Gumi. See [API Keys and Tokens](api-keys-and-tokens.md) and the [Hermes Integration quickstart](hermes-integration.md#quickstart-from-bootstrap-to-first-message).
5. **Day-to-day**: see [Daily Operations](daily-operations.md) for the routine.

If something breaks, see [Troubleshooting](troubleshooting.md) before re-running setup.

## What to read next

| If you want to... | Go to |
|---|---|
| Understand the ethical model before deploying anything | [Ethics](../ethics/index.md) |
| Know what facets actually represent | [Facet Model](../concepts/facet-model.md) |
| See what the system can and cannot do | [Limitations](../research/limitations.md) |
| Run an evaluation | [Running Evaluations](running-evaluations.md) |
| Cite Relic in a paper | [Citing Relic](../research/citing-relic.md) |

## Hard rules to internalize before any real use

- Synthetic data or explicitly consented data only.
- The subject can always pause, export, correct, and delete.
- Safety signals are researcher-facing: never shown to the subject, never injected into Gumi's memory.
- Gumi's own diegetic events are not evidence about the subject.
- Treat every facet as an estimate, not a fact. Read its confidence score and source trace.

These rules are enforced by the architecture and the test suite, not by convention. They are also documented in [Ethics](../ethics/index.md).
