# Demo Quickstart

Use this when you want to see Relic running in minutes without going through the full 15-step bootstrap TUI. Two paths: a **local demo bundle** (no install needed beyond Python) and a **canned demo subject** loaded into the workbench.

## Path A: End-to-end demo bundle

Runs the eval pipeline against synthetic fixtures, computes metrics, produces a replication bundle. No network, no model calls, no private data. Good for "does this even work on my machine."

```bash
python scripts/demo_e2e.py            # full run
python scripts/demo_e2e.py --dry-run  # preview, no writes
python scripts/demo_e2e.py -v         # verbose
```

Output: a replication bundle ZIP at `artifacts/replication_bundles/demo-e2e-<timestamp>.zip` containing `manifest.json`, `traces.jsonl`, `policy_snapshot.json`, `report.json`, and `checksums.json` (the minimal-bundle profile; see `replication/README.md`). Unzip it to inspect, or feed it back to a peer for independent reproduction.

## Path B: Pre-generated demo subject for the workbench

Loads a synthetic subject with sessions, facets, corrections, and CAC traces already populated. Skip bootstrap entirely.

```bash
# 1. Generate the demo SQLite DB and JSON export.
python scripts/generate_demo_data.py --out-dir demo/generated

# 2. Point the workbench at the demo DB.
RELIC_DB_PATH=demo/generated/relic.db relic ui

# 3. Open http://localhost:8080 and pick "demo-subject".
```

The default output dir `demo/generated/` is gitignored under `.gitignore`. A canned `demo_data.json` is committed so you can poke at the shape without running the generator.

To regenerate with different randomness:

```bash
python scripts/generate_demo_data.py --out-dir demo/generated  # idempotent by content
```

## Path C: Live workbench demo (no install)

The repo deploys a static workbench build to GitHub Pages:

> [yuzushi-dev.github.io/Relic/](https://yuzushi-dev.github.io/Relic/)

It runs entirely in the browser against the committed `demo/generated/demo_data.json`. No backend. Use it to evaluate the UI shape before deciding to install. The local install is what you want for real research; the live demo is a brochure.

## When to use which

| You want to... | Use |
|---|---|
| Evaluate the UI without installing | Path C (live demo) |
| Reproduce eval metrics on your machine | Path A (`demo_e2e.py`) |
| Inspect a populated subject in the local workbench | Path B (`generate_demo_data.py`) |
| Actually study a subject (real or synthetic, full pipeline) | [First Subject](first-subject.md) |

## Fixtures behind the demos

Demo data is drawn from `fixtures/`. Each subdirectory has a `README.md` describing the scenario. The high-value ones:

- `fixtures/basic/`: minimal happy path.
- `fixtures/gumi-eval/`: identity stability and roleplay admission cases.
- `fixtures/corrections/`: researcher feedback events and propagation.
- `fixtures/memory-dynamics/`: decay/reinforcement scenarios.
- `fixtures/shared-continuity/`: subject-confirmed marker lifecycle.
- `fixtures/researcher-workbench/`: workbench-facing inputs.

To list everything:

```bash
python -m relic.eval.fixtures list
```

Fixtures are versioned. Do not edit them in place; create new directories for new scenarios. See [Fixtures reference](../reference/fixtures.md).

## Cleaning up

```bash
rm -rf demo/generated artifacts/demo-bundle-*
```

This removes only generated artefacts; the committed `demo_data.json` and the `fixtures/` tree are untouched.
