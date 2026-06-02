# Model Management

How to pick, install, swap, and tune the local LLM Relic uses through Ollama.

## What the model is used for

Three call sites:

1. **Bootstrap data generation**: Gumi background, intro composition, media constraints. Runs at subject creation and on regeneration. A few dozen calls per subject lifetime.
2. **Runtime conversation**: every turn the subject sends. The bulk of LLM usage in active deployments.
3. **Evaluation**: `scripts/eval_run.py` and the eval harness. Use a deterministic mock model by default; only call the real model when you specifically need to.

The same model serves all three by default, but you can split them (see [Splitting models per call site](#splitting-models-per-call-site)).

## Defaults

Defined in `relic/hermes_runtime.py`:

| Variable | Default |
|---|---|
| `HERMES_DEFAULT_MODEL` | `qwen2.5:32b-instruct-q4_K_M` |
| `HERMES_OLLAMA_BASE_URL` | `http://localhost:11434/v1` |
| `HERMES_CONTEXT_LENGTH` | `65536` |

The default is a 4-bit quantised 32B model. Reasonable quality, ~20 GB on disk, comfortable on 24 GB RAM with no GPU.

## Choosing a model

| Hardware | Suggested model | Disk | Min RAM | Tradeoff |
|---|---|---|---|---|
| 32 GB RAM, no GPU | `qwen2.5:32b-instruct-q4_K_M` (default) | ~20 GB | 24 GB | Good balance |
| 16 GB RAM, no GPU | `llama3.2:3b` | ~2 GB | 8 GB | Lower output quality, especially on roleplay admission |
| 16 GB RAM + GPU | `qwen2.5:14b-instruct-q4_K_M` | ~9 GB | 12 GB | Good quality, fast on GPU |
| 64 GB+ RAM, beefy GPU | `qwen2.5:72b-instruct-q4_K_M` | ~45 GB | 48 GB | Best quality, slow without GPU |
| Anything | `mistral:7b-instruct` | ~4 GB | 8 GB | OK fallback |

Quality on Relic-specific tasks (identity stability, roleplay admission, non-clinical language) drops sharply below ~14B parameters at 4-bit. Use eval to confirm before standardising on a smaller model.

## Pulling a model

```bash
ollama pull <model-tag>
ollama list                    # what's installed
```

Pulls go to `~/.ollama/models/`. Each is multi-GB; check disk before pulling several.

## Swapping the active model

Three layers to keep in sync.

### 1. Ollama-side: nothing to do

`ollama pull` is enough; Ollama serves all installed models on demand.

### 2. Hermes-side: update the config

```bash
hermes config set model.default <new-model-tag>
hermes config set model.context_length <ctx_window>   # optional
hermes config get model                                # verify
```

Restart any running Hermes gateway: `pkill -f 'hermes gateway run'`, then start again.

### 3. Relic-side: nothing if Hermes is the model client

Relic talks to Hermes; Hermes talks to Ollama. As long as Hermes is configured, Relic uses whatever Hermes uses.

If you set `HINDSIGHT_LLM_API_KEY` to use a non-Ollama Hindsight backend, Hindsight has its own model setting, see [Hindsight LLM API key](api-keys-and-tokens.md#hindsight-llm-api-key).

## Verifying the swap

```bash
relic runtime doctor              # checks model availability through Hermes
ollama run <new-model> "ping"     # direct sanity check
```

Then run a short eval slice:

```bash
python scripts/eval_run.py --module gumi_roleplay
```

Compare `mode_switch_accuracy`, `persona_intrusion_cost`, and `clinicalization_rate` against your prior baseline (record one first with `--record-baseline`).

## Splitting models per call site

Useful if you want a strong model for runtime conversation but a cheap one for batch eval or bootstrap.

- **Runtime conversation**: configured via `hermes config set model.default ...`. This is what governs production behavior.
- **Bootstrap & intro composition**: generation uses whatever Hermes returns; there is no separate switch in the OSS distribution. Adjust by overriding the Hermes model before running `relic subject create`, then restoring after.
- **Evaluation**: pass `--mock-model` to `scripts/eval_run.py` to skip live inference entirely. For non-mock runs, the harness inherits Hermes's setting.

## Memory usage and concurrency

Ollama loads one model into RAM and keeps it warm. Switching models forces an unload + reload. If you split runtime and eval models, expect:

- ~15–30 seconds reload time when switching between two 32B models on 32 GB RAM.
- Active model evicted when the other is requested. Predicate: "warm only the model you are about to use."

For concurrent subjects you still run a single Ollama and a single Hermes gateway per subject. Throughput is bounded by Ollama tokens-per-second, not by the number of gateways.

## When to retrain expectations

If you swap to a noticeably different model (e.g. 3B → 32B, or 32B → 72B):

- Re-baseline the eval (`python scripts/eval_run.py --record-baseline`).
- Re-read SOUL.md for each subject and confirm the relational distance is still calibrated. Stronger models often produce subtly different Gumi voices.
- Consider regenerating Gumi backgrounds for active subjects via `relic-profile gumi generate <subject_id>` after backing up.

## Troubleshooting

- **`relic runtime doctor` fails on "model not available"**: confirm `ollama list` shows the tag and `hermes config get model.default` matches.
- **Slow first response after a swap**: model is warming up. Subsequent turns are fast.
- **Out-of-memory crashes after a swap**: model is too large for available RAM. Drop to a smaller quantisation (`q4_K_S` instead of `q4_K_M`, or move to a smaller parameter count).
- **Quality regression after a swap**: rerun eval and look at the per-metric deltas; a 3B model is not a drop-in for a 32B model for this workload.
