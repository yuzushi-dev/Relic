# Performance Expectations

What "normal" looks like, what's slow, what's broken. Numbers below are baselines on the reference machine (Linux, 32 GB RAM, no GPU, default `qwen2.5:32b-instruct-q4_K_M`). Adjust expectations by hardware.

These are not benchmarks. They are operational sanity checks.

## Bootstrap (per subject)

| Step | Typical | Slow but OK | Investigate |
|---|---|---|---|
| Item battery (TIPI + ECR-RS + project items) | 8–12 min | up to 20 min | researcher pacing varies |
| Self-report + researcher-coded + boundaries | 5–10 min | up to 15 min | same |
| Consent record | 1–2 min | 3 min | — |
| Gumi background generation (hybrid mode) | 30–90 s | 3 min | > 3 min: check Ollama load |
| First media canon generation (if enabled) | 1–3 min | 5 min | > 5 min: Gemini quota or network |
| Total researcher time | 30–60 min | 90 min | structural — keep sessions short |

The TUI is gated on the researcher's typing speed, not on the model. Most of the elapsed time is human, not machine.

## Runtime per turn

| Phase | Typical | Slow but OK | Investigate |
|---|---|---|---|
| `pre_llm_call` (admission, memory, CAC) | 50–200 ms | 500 ms | > 500 ms: `chronicle decision --kind cac_decision`, look for hot scorer paths |
| LLM call (32B model, CPU) | 4–15 s | 25 s | > 30 s: Ollama swap, OOM, model warm-up |
| LLM call (32B model, 24 GB GPU) | 1–3 s | 6 s | > 10 s: check GPU memory and concurrent loads |
| LLM call (3B model, CPU) | 1–3 s | 5 s | > 8 s: CPU contention |
| `post_llm_call` (critic, continuity write, output safety) | 100–400 ms | 1 s | > 1 s: provider write latency |
| Total wall-clock | 5–16 s (CPU) / 2–4 s (GPU) | 30 s (CPU) | > 30 s on CPU: see [Troubleshooting](../guides/troubleshooting.md) |

First turn after gateway start is always slower (model load + warm-up). Subsequent turns settle to the baseline.

## Idle Hermes gateway

| Metric | Baseline | Notes |
|---|---|---|
| RAM | 200–400 MB (Hermes) + 18–24 GB (Ollama warm model) | Ollama unloads idle models after ~5 min |
| CPU | < 1% | Cron ticks every 60 s — brief spikes are normal |
| Disk writes | a few KB/min | Cron decisions, retention reaper if scheduled |

If RAM grows beyond the baseline over hours, suspect a memory leak in the plugin or in the model — restart the gateway, file an issue.

## Workbench

| Action | Typical | Slow but OK | Investigate |
|---|---|---|---|
| Page load (subject overview) | < 500 ms | 1.5 s | > 2 s: SQLite locked or many corrections to render |
| Timeline render (200 events) | < 800 ms | 2 s | > 2 s: paginate via `--limit` instead |
| Correction submit + recompile queue | < 200 ms (UI), 2–10 s (recompile) | 20 s recompile | > 30 s: too many cascading artifacts; consider a smaller correction scope |

The workbench is a thin reader. If a page is slow, the bottleneck is usually the DB or the recompile, not the UI.

## Chronicle queries

| Query | Typical |
|---|---|
| `chronicle query --subject ID --limit 100` | < 200 ms |
| `chronicle timeline --subject ID --since 24h` | < 500 ms |
| `chronicle stats --subject ID --since 30d` | < 1 s |
| `chronicle provenance --artifact ID --depth 3` | < 500 ms |
| `chronicle reaper --dry-run` (over 1 yr of events for a few subjects) | a few seconds |

Indexes cover the common access patterns. If a query is slow, it usually means the filter is too broad — add `--subject`, `--since`, `--limit`.

## Concurrency

- **One Ollama daemon** serves many gateways. Throughput is bounded by tokens-per-second, not by the number of gateways.
- **One gateway per subject** (recommended). They don't share state at runtime; sharing creates audit confusion.
- **SQLite has one writer at a time.** The workbench, the gateway, and CLI commands all contend for the write lock briefly. Heavy parallel use (>3 gateways writing simultaneously) will show contention. For that scale, plan the SQLite → Postgres move (see [Schema Migrations](../guides/schema-migrations.md)).

## Disk growth

| Subject | Per month |
|---|---|
| Light interaction (a few turns/day) | ~5–10 MB |
| Heavy interaction (dozens of turns/day, media on) | 50–200 MB |
| Add media canons (images, voice) | + 50–200 MB per generation cycle |

Run `chronicle reaper --dry-run` periodically to see what would be cleaned. By default `standard_365d` events stay one year; you will not see meaningful pressure for the first year unless media is on.

## How to capture your own baseline

```bash
# Time a turn end-to-end (approximate).
time relic runtime doctor

# Look at recent decision latencies.
chronicle decision --subject <subject_id> --kind cac_decision --limit 20 \
  --format json | jq '.[].payload.elapsed_ms'

# Watch Ollama:
ollama ps
```

For systematic measurement, integrate with your usual observability stack (Prometheus, OpenTelemetry). Relic does not ship its own metrics endpoint.
