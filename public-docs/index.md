# Relic

**Status: OSS Alpha** | Python 3.10+ | AGPL-3.0

Relic is a runtime governance and longitudinal modeling layer for conversational agents. It captures behavioral signals from interaction, maintains evolving subject profiles, and produces inspectable runtime context under privacy, correction, and provenance constraints.

The system is designed for research contexts where the goal is to observe and model behavioral patterns over time, not to generate static character descriptions. Profiles start from structured bootstrap data and evolve through interaction, elicitation, correction, and review. Every trait carries a confidence score and a source trace. The system explicitly represents what it does not know.

Relic is paired with [Gumi](concepts/relic-and-gumi.md), a diegetic relational agent that runs on top of the governance layer. Gumi has her own voice, background, and relational continuity; Relic manages the underlying profile, privacy gates, and artifact authority.

## Who this is for

| If you are... | Start here |
|---|---|
| New here and want a 5-minute orientation | [Getting Started](guides/getting-started.md) |
| A researcher evaluating the system | [Theoretical Grounding](research/theoretical-grounding.md), [Limitations](research/limitations.md) |
| Setting up a new deployment | [Installation](guides/installation.md), [First Subject](guides/first-subject.md) |
| Looking for how to get a Telegram bot / API key | [API Keys and Tokens](guides/api-keys-and-tokens.md) |
| Reviewing data or correcting outputs | [Researcher Workbench](guides/researcher-workbench.md), [Corrections](guides/corrections-and-replay.md) |
| Stuck on an error | [Troubleshooting](guides/troubleshooting.md), [FAQ](reference/faq.md) |
| Contributing code | [Contributing](contributing/index.md), [Release Status](contributing/release-status.md) |
| Assessing the ethics of the system | [Ethics](ethics/index.md) |

## Ethics

This project operates in a sensitive domain. Read the [ethics section](ethics/index.md) before deploying or contributing. The short version:

- Relic models interaction patterns; it does not diagnose, assess, or clinically evaluate anyone.
- Every facet is an estimate with a confidence score, not a ground truth.
- Subjects can export, correct, pause, and delete their data.
- Gumi's diegetic events are not evidence about the subject.
- Safety signals are visible to researchers only, never to subjects or the agent.

## Quick start

```bash
git clone https://github.com/yuzushi-dev/Relic
cd Relic
pip install -e .
relic init          # first-run setup: Ollama, Hermes (optional)
relic subject create
```

See [Installation](guides/installation.md) for full prerequisites and [First Subject](guides/first-subject.md) for a walkthrough using synthetic demo data.

## License

[AGPL-3.0](https://github.com/yuzushi-dev/Relic/blob/main/LICENSE.txt). If you use Relic in a product or network service, your modifications must be open source.
