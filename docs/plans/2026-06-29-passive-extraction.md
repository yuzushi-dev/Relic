# Passive Observation Extraction Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Turn the subject's free-form Telegram messages into facet observations (not just check-in replies), so trait coverage advances from natural conversation, gated by explicit consent and validated by a cross-family attribution jury.

**Architecture:** A new `passive_extractor` reads `role='user'` messages from the Hermes `state.db` since a per-subject watermark, generates candidate facets per message (lexical pre-rank), confirms the target facet with a cross-family jury (reused from the existing dev validator, extracted into an importable module), extracts a signal for the confirmed facet, and writes a `source_type='passive_chat'` observation. The existing `synthesize_traits` (already wired) folds these into trait confidence. It runs inside the existing `memory_sync` cron, behind a `consent_for_passive_extraction` opt-in flag.

**Tech Stack:** Python 3.10+, stdlib `sqlite3`/`urllib`, Ollama cloud endpoint (gemma4:31b-cloud / gpt-oss:120b-cloud / minimax-m3:cloud), pytest.

---

## Background (read before starting)

- Source data: Hermes `state.db` → `messages(role, content, timestamp)`. Already read by `relic/checkin/context_builder.py:291` (`build_recent_subject_messages_section`) — copy its query/filters (`role='user'`, `content NOT LIKE '[IMPORTANT:%'`).
- Existing jury: `scripts/dev/validate_attribution_jury.py` — cross-family panel (`JUDGES` = gemma4:31b-cloud / gpt-oss:120b-cloud / minimax-m3:cloud), forced-choice `_llm_choose`, deterministic lexical voter `_lexical_best`, candidate grounding `_candidates`, aggregation `_aggregate`, thresholds `SAMPLES`/`N_VOTERS`/`AGREE_MIN`. Currently a script, not importable.
- Signal extraction: `relic/checkin/facet_updater.py` → `extract_observation()` / `_call_llm_extract()` (gemma4:31b-cloud, env `RELIC_OLLAMA_MODEL`). Returns `informative`, `signal_position`, `signal_strength`, `confidence_delta`, `observation_summary`, `error`.
- Trait synthesis: `relic/checkin/facet_updater.py` → `synthesize_traits()` already consumes `source_type='passive_chat'` observations. **No change needed** — passive obs flow into traits automatically on the next synthesis pass.
- Governance constraints (do NOT skip):
  - confidence cap stays `MULTI_EVIDENCE_CAP = 0.55` (single-source) — synthesis already enforces this.
  - strip the Telegram `[Replying to: "..."]` scaffold with `relic.checkin.reply_capture.strip_reply_quote_prefix` before any LLM sees the text (anti-bleed; see `project_diegetic_bleed_followup`).
  - skip non-substantive messages — reuse `relic.checkin.reply_capture._is_substantive`.
  - idempotency: never re-process a message; advance a per-subject watermark.
  - consent: a new `consent_for_passive_extraction` flag in `delivery_policy.json`, default OFF.
- `observations` schema (`relic/checkin/db_init.py:61`): `facet_id, source_type, source_ref, content, extracted_signal, signal_strength, signal_position, conversation_domain, created_at`. `INSERT OR IGNORE` on `(facet_id, source_ref)` dedupes (mirror `facet_updater.py:419`).

Run the full check-in suite after each task: `python -m pytest tests/checkin/ -p no:xdist -q` (machine is weak — sequential, no xdist; never run the 4 slow/LLM files ignored in `pyproject.toml`).

---

## Task 1: Extract the jury into an importable module

Move the reusable jury core out of the dev script so both the validator and the passive extractor share one implementation (DRY). The script keeps working by importing from the module.

**Files:**
- Create: `relic/checkin/attribution_jury.py`
- Modify: `scripts/dev/validate_attribution_jury.py` (replace inlined helpers with imports)
- Test: `tests/checkin/test_attribution_jury.py`

**Step 1: Write the failing test** (pure, deterministic pieces only — no network)

```python
# tests/checkin/test_attribution_jury.py
from relic.checkin.attribution_jury import tokens, lexical_best, aggregate, JUDGES

def test_tokens_lowercases_and_splits():
    assert tokens("Ciao, Mondo!") == {"ciao", "mondo"}

def test_lexical_best_picks_highest_overlap():
    facets = {
        "a.x": {"name": "rischio", "description": "propensione al rischio", "spectrum_low": "", "spectrum_high": ""},
        "b.y": {"name": "umorismo", "description": "stile umorismo", "spectrum_low": "", "spectrum_high": ""},
    }
    cands = [{"id": "a.x", **facets["a.x"]}, {"id": "b.y", **facets["b.y"]}]
    assert lexical_best("ho corso un grosso rischio", cands, facets) == "a.x"

def test_aggregate_flags_on_majority_reject():
    # recorded facet rejected by a strict majority of voters
    out = aggregate("a.x", votes=["b.y", "b.y", "b.y", "a.x"], by_judge={})
    assert out["flagged"] is True
    assert out["agreed"] == "b.y"

def test_judges_are_three_distinct_families():
    families = {m.split(":")[0].split("-")[0] for m, _ in JUDGES}
    assert {"gemma4", "gpt", "minimax"} <= families or len(JUDGES) == 3
```

**Step 2: Run to verify it fails**

Run: `python -m pytest tests/checkin/test_attribution_jury.py -v`
Expected: FAIL with `ModuleNotFoundError: relic.checkin.attribution_jury`

**Step 3: Create the module**

Move these symbols verbatim from `scripts/dev/validate_attribution_jury.py` into `relic/checkin/attribution_jury.py`, renaming the private ones to public where the tests need them: `_load_keys`, `_next_key`, endpoint/`JUDGES`/`SAMPLES`/`N_VOTERS`/`AGREE_MIN` constants, `tokens` (was `_tokens`), `llm_choose` (was `_llm_choose`), `candidates` (was `_candidates`), `lexical_best` (was `_lexical_best`), `aggregate` (was `_aggregate`). Keep the network code identical. Add a thin module docstring pointing back to Verga et al. 2404.18796.

**Step 4: Point the script at the module**

In `scripts/dev/validate_attribution_jury.py` replace the moved definitions with:
```python
from relic.checkin.attribution_jury import (
    JUDGES, SAMPLES, N_VOTERS, AGREE_MIN,
    tokens as _tokens, llm_choose as _llm_choose,
    candidates as _candidates, lexical_best as _lexical_best,
    aggregate as _aggregate,
)
```
Leave the script's `validate_all` / `apply_verdicts` / `main` in place.

**Step 5: Run tests + a script smoke**

Run: `python -m pytest tests/checkin/test_attribution_jury.py -v`
Expected: PASS
Run: `python scripts/dev/validate_attribution_jury.py --help`
Expected: argparse help prints (no ImportError)

**Step 6: Commit**

```bash
git add relic/checkin/attribution_jury.py scripts/dev/validate_attribution_jury.py tests/checkin/test_attribution_jury.py
git commit -m "refactor(checkin): extract attribution jury into importable module"
```

---

## Task 2: Per-subject watermark for processed messages

Idempotency: track the last `state.db` message timestamp consumed, per subject, in `relic.db`.

**Files:**
- Modify: `relic/checkin/db_init.py` (add table to the schema string + bump schema_version)
- Create: `relic/checkin/passive_state.py` (read/advance watermark)
- Test: `tests/checkin/test_passive_state.py`

**Step 1: Write the failing test**

```python
# tests/checkin/test_passive_state.py
from relic.checkin.db_init import init_db
from relic.checkin.passive_state import get_watermark, set_watermark

def test_watermark_defaults_to_zero(tmp_path):
    conn = init_db(tmp_path / "r.db")
    assert get_watermark(conn, "daniele") == 0.0

def test_watermark_roundtrip_monotonic(tmp_path):
    conn = init_db(tmp_path / "r.db")
    set_watermark(conn, "daniele", 100.0)
    assert get_watermark(conn, "daniele") == 100.0
    set_watermark(conn, "daniele", 50.0)   # never moves backward
    assert get_watermark(conn, "daniele") == 100.0
```

**Step 2: Run to verify it fails** — `ModuleNotFoundError`.

**Step 3: Add the table** in `relic/checkin/db_init.py` schema string:
```sql
CREATE TABLE IF NOT EXISTS passive_extraction_state (
    subject_id TEXT PRIMARY KEY,
    last_processed_ts REAL NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT ''
);
```

**Step 4: Implement** `relic/checkin/passive_state.py`:
```python
from __future__ import annotations
import sqlite3
from datetime import datetime, timezone

def get_watermark(conn: sqlite3.Connection, subject_id: str) -> float:
    row = conn.execute(
        "SELECT last_processed_ts FROM passive_extraction_state WHERE subject_id=?",
        (subject_id,),
    ).fetchone()
    return float(row[0]) if row else 0.0

def set_watermark(conn: sqlite3.Connection, subject_id: str, ts: float) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO passive_extraction_state (subject_id, last_processed_ts, updated_at)
           VALUES (?, ?, ?)
           ON CONFLICT(subject_id) DO UPDATE SET
               last_processed_ts = MAX(passive_extraction_state.last_processed_ts, excluded.last_processed_ts),
               updated_at = excluded.updated_at""",
        (subject_id, float(ts), now),
    )
    conn.commit()
```

**Step 5: Run tests** — PASS.

**Step 6: Commit**
```bash
git add relic/checkin/db_init.py relic/checkin/passive_state.py tests/checkin/test_passive_state.py
git commit -m "feat(checkin): per-subject passive-extraction watermark"
```

---

## Task 3: Read + clean candidate messages from state.db

Pull unprocessed, substantive, scaffold-stripped subject messages newer than the watermark.

**Files:**
- Create: `relic/checkin/passive_extractor.py` (function `load_new_messages`)
- Test: `tests/checkin/test_passive_extractor.py`

**Step 1: Failing test** — build a temp `state.db` with a `messages` table; assert the loader returns only `role='user'`, substantive, non-`[IMPORTANT:` rows after the cutoff, with the `[Replying to: "..."]` prefix stripped, ordered ascending by timestamp.

```python
def test_load_new_messages_filters_and_cleans(tmp_path):
    state = tmp_path / "state.db"
    import sqlite3
    c = sqlite3.connect(state)
    c.execute("CREATE TABLE messages (role TEXT, content TEXT, timestamp REAL)")
    c.executemany("INSERT INTO messages VALUES (?,?,?)", [
        ("user", "[IMPORTANT: cron prompt]", 10),
        ("assistant", "ciao", 11),
        ("user", "ok", 12),                                   # too short / dismissal
        ("user", '[Replying to: "x"] Ho corso un grosso rischio oggi', 13),
        ("user", "Mi sono fermato a riflettere sulla giornata", 20),
    ])
    c.commit(); c.close()
    from relic.checkin.passive_extractor import load_new_messages
    msgs = load_new_messages(state, since_ts=5.0)
    texts = [m["text"] for m in msgs]
    assert texts == ["Ho corso un grosso rischio oggi", "Mi sono fermato a riflettere sulla giornata"]
    assert msgs[-1]["ts"] == 20
```

**Step 2: Run — fails.**

**Step 3: Implement** `load_new_messages(state_db_path, since_ts, limit=20)`: mirror `context_builder.py:314-328` query but `timestamp > since_ts ORDER BY timestamp ASC LIMIT ?`; for each row apply `strip_reply_quote_prefix` then `_is_substantive`; return `[{"ts": float, "text": str}]`. Fail-open to `[]` on any sqlite error (log WARNING). Cap `limit` to bound jury cost per run.

**Step 4: Run — PASS.**

**Step 5: Commit**
```bash
git add relic/checkin/passive_extractor.py tests/checkin/test_passive_extractor.py
git commit -m "feat(checkin): load+clean passive subject messages"
```

---

## Task 4: Attribute a message to a facet via the jury

Given one cleaned message, pick the facet it evidences (or NONE) with the cross-family jury.

**Files:**
- Modify: `relic/checkin/passive_extractor.py` (add `attribute_message`)
- Test: `tests/checkin/test_passive_extractor.py` (inject a fake panel — no network)

**CRITICAL — reuse the jury correctly (the existing functions are validation-shaped):**
The jury was built to *validate a recorded facet*, not to attribute from scratch. Verified shapes (read `relic/checkin/attribution_jury.py`):
- `aggregate(recorded, votes, by_judge)` returns `{votes, keep_votes, reject_votes, judge_choice, families_rejecting, action, target}`. It confirms only when `cast>=3 AND reject>=majority AND plurality!=recorded AND families_rejecting>=2`; then `action="reattribute"`/`target=plurality` (or `action="drop"`/`target=None` if plurality is `"NONE"`), else `action="keep"`/`target=recorded`.
- `candidates(conn, recorded, siblings, reply, facets)` does NOT touch `conn`, but it indexes `facets[recorded]` — so you must NOT pass `recorded="NONE"` to it (KeyError, "NONE" is not a facet).
- `llm_choose(model, reply, question, candidates, ...)` already adds `"NONE"` to the valid vote set itself, so the candidate list must contain only real facets.

**The fresh-attribution recipe (no recorded facet):**
1. Add a small helper to `relic/checkin/attribution_jury.py` (DRY, next to `lexical_best`):
   ```python
   def lexical_candidates(reply: str, facets: dict, k: int = 4) -> list[dict]:
       """Top-k facets by lexical overlap with the message — the candidate slate
       for fresh attribution (the panel may still vote NONE)."""
       rt = tokens(reply)
       scored = sorted(
           ((fid, len(rt & tokens(f["name"] + " " + f["description"] + " "
                                  + (f.get("spectrum_low") or "") + " "
                                  + (f.get("spectrum_high") or ""))))
            for fid, f in facets.items()),
           key=lambda x: -x[1],
       )
       return [dict(id=fid, name=facets[fid]["name"], description=facets[fid]["description"])
               for fid, sc in scored[:k] if sc > 0]
   ```
2. In `passive_extractor.attribute_message`: build `cands = lexical_candidates(text, facets)`. If empty → return `None`. Run the panel: for each `(model, _)` in `JUDGES`, `SAMPLES` times, shuffle `cands` (use the passed `rng`) and call `judge_fn(model, reply=text, question="", candidates=cands, ...)`; collect into `votes` and `by_judge[model]`. Append the deterministic voter `lexical_best(text, cands, facets)` to `votes`.
3. Call `aggregate(recorded="NONE", votes=votes, by_judge=by_judge)`. With `recorded="NONE"`, a real facet only wins when the panel reaches majority + ≥2 families on it; `target` is that facet. Return `result["target"]` when it is a real facet id (not `None` and not `"NONE"`), else `None`.

**Step 1: Failing test** (no network — inject `judge_fn`)

```python
def _facets(conn):
    return {r[0]: {"name": r[1], "description": r[2], "spectrum_low": r[3], "spectrum_high": r[4]}
            for r in conn.execute("SELECT id,name,description,spectrum_low,spectrum_high FROM facets")}

def test_attribute_message_jury_picks_facet(tmp_path):
    from relic.checkin.db_init import init_db, seed_facets
    from relic.checkin.passive_extractor import attribute_message
    conn = init_db(tmp_path / "r.db"); seed_facets(conn)
    facets = _facets(conn)
    target = "cognitive.risk_tolerance"
    assert target in facets
    # fake panel: every judge always votes the target → majority + all families
    fake = lambda model, reply, question, candidates, **kw: target
    got = attribute_message("ho corso un grosso rischio", facets, judge_fn=fake)
    assert got == target

def test_attribute_message_none_when_panel_abstains(tmp_path):
    from relic.checkin.db_init import init_db, seed_facets
    from relic.checkin.passive_extractor import attribute_message
    conn = init_db(tmp_path / "r.db"); seed_facets(conn)
    facets = _facets(conn)
    fake = lambda *a, **k: "NONE"
    assert attribute_message("ciao come va oggi", facets, judge_fn=fake) is None
```
(If `seed_facets` lacks `cognitive.risk_tolerance`, pick any seeded id with lexical overlap and adjust the message text; keep the assertion on that id.)

**Step 2: Run — fails.**

**Step 3: Implement** `lexical_candidates` (in `attribution_jury.py`) and `attribute_message(text, facets, *, judge_fn=None, rng=None)` (in `passive_extractor.py`) per the recipe above. `judge_fn` defaults to `attribution_jury.llm_choose`; `rng` defaults to a fresh `random.Random()`.

**Step 4: Run — PASS** (`python -m pytest tests/checkin/test_passive_extractor.py -v`).

**Step 5: Commit** (explicit paths — never `-a`/`-A`)
```bash
git add relic/checkin/attribution_jury.py relic/checkin/passive_extractor.py tests/checkin/test_passive_extractor.py
git commit -m "feat(checkin): jury-based facet attribution for passive messages"
```

---

## Task 5: Extract a signal + write the observation

For a confirmed (message, facet) pair, get `signal_position`/`signal_strength` and persist a `passive_chat` observation.

**Files:**
- Modify: `relic/checkin/passive_extractor.py` (add `extract_and_write`)
- Test: `tests/checkin/test_passive_extractor.py`

**Design:** reuse `facet_updater.extract_observation` but pass the message as `reply_text` and a synthesized `question_text` like `"(osservazione passiva) {facet description}"` so the existing extractor produces a signal. Drop observations with `signal_strength < PASSIVE_STRENGTH_FLOOR` (e.g. 0.5) — passive evidence must be clear. Insert with `INSERT OR IGNORE` (`source_ref = f"msg:{int(ts)}"`, `source_type='passive_chat'`). Do NOT touch traits here — `synthesize_traits` owns that.

**Step 1: Failing test** — inject a fake `llm_client` returning a strong signal; assert one row lands in `observations` with `source_type='passive_chat'` and the right `facet_id`; assert a weak-signal extraction writes nothing.

**Step 2–4:** implement, run, PASS.

**Step 5: Commit** (explicit paths)
```bash
git add relic/checkin/passive_extractor.py tests/checkin/test_passive_extractor.py
git commit -m "feat(checkin): write passive_chat observations with strength floor"
```

---

## Task 6: Orchestrate one subject end-to-end (consent-gated, watermarked)

Tie Tasks 3–5 together into `run_passive_extraction(conn, subject_id, state_db_path, facets, *, dry_run)`.

**Files:**
- Modify: `relic/checkin/passive_extractor.py` (add `run_passive_extraction`)
- Test: `tests/checkin/test_passive_extractor.py`

**Design:**
1. Load `delivery_policy.json`; return early `{"skipped": "no_consent"}` unless `consent_for_passive_extraction` is true.
2. `since = get_watermark(conn, subject_id)`; `msgs = load_new_messages(state_db_path, since)`.
3. For each msg: `facet = attribute_message(...)`; if facet, `extract_and_write(...)`.
4. After the loop, `set_watermark(conn, subject_id, max(ts))` (only if not dry_run).
5. Return counts `{processed, attributed, written, watermark}`.

**Step 1: Failing test** — full path with fakes (fake judge + fake llm_client + temp state.db + consent on): assert observations written and watermark advanced; a second run with no new messages writes nothing; consent-off short-circuits.

**Step 2–4:** implement, run, PASS.

**Step 5: Commit** (explicit paths)
```bash
git add relic/checkin/passive_extractor.py tests/checkin/test_passive_extractor.py
git commit -m "feat(checkin): end-to-end consent-gated passive extraction per subject"
```

---

## Task 7: Wire into the memory_sync cron

Run passive extraction for each subject in the existing 30-minute cron, before synthesis picks it up.

**Files:**
- Modify: `relic/gumi_plugin/memory_sync.py` (`_process_pending_facets`, ~line 400-410)
- Modify: `relic/checkin/passive_extractor.py` (add `main()` CLI: `--subject-id`, `--dry-run`, `--since`)
- Test: `tests/checkin/test_passive_extractor.py` (CLI dry-run smoke on a temp home)

**Design:** in the per-subject loop, after `process_pending_exchanges`, call `run_passive_extraction` inside its own try/except (per-subject isolation, fail-open — must not break the cron stdout contract). Resolve `state_db_path` from the Hermes home for that profile (document the path resolution; reuse however `context_builder` locates `state.db`). Load facets once per subject from `relic.db`. Synthesis already runs in `process_pending_exchanges` → no extra wiring.

**Step 5: Commit**
```bash
git commit -am "feat(checkin): run passive extraction inside memory_sync cron"
```

---

## Task 8: Provisioning — the consent flag

Make `consent_for_passive_extraction` a real, defaulted, documented field.

**Files:**
- Modify: wherever `delivery_policy.json` is templated in provisioning (grep `consent_for_active_elicitation` to find it).
- Modify: `public-docs/architecture/security-model.md` (document the opt-in + that passive obs are capped at 0.55 and jury-validated).
- Test: a provisioning/unit test asserting the flag defaults to `false`.

**Step 5: Commit**
```bash
git commit -am "feat(provisioning): add consent_for_passive_extraction opt-in (default off)"
```

---

## Rollout (manual, after merge — NOT part of TDD)

1. Full suite: `python -m pytest tests/checkin/ -p no:xdist -q` → all green.
2. Backup live DBs: `cp ~/.relic/subjects/<id>/relic.db backups/relic.db.bak_passive_$(date +%Y%m%d_%H%M%S)`.
3. Dry-run on daniele to inspect what it WOULD extract:
   `python -m relic.checkin.passive_extractor --subject-id daniele --dry-run`
   Review attributed facets for mis-attribution before enabling.
4. Enable `consent_for_passive_extraction: true` for daniele/barbara in `delivery_policy.json` (their data — confirm with the user first; outward-facing).
5. Restart gateways: `systemctl --user restart hermes-gateway-gumi-daniele.service hermes-gateway-gumi-barbara.service`.
6. After a day, recheck coverage (`/tmp/coverage_daniele.py` equivalent) and `SELECT COUNT(*) FROM observations WHERE source_type='passive_chat' AND created_at > <enable_ts>`.

## Risks / watch-items

- **Jury cost:** 3 families × `SAMPLES` per message. The `limit` in `load_new_messages` and the substantive pre-filter bound it. If the Ollama weekly cap trips (see `project_ollama_weekly_cap_outage`), passive extraction must fail-open and not stall the cron.
- **Mis-attribution:** the jury + strength floor are the mitigations; the dry-run review (rollout step 3) is the human gate before live.
- **Privacy:** store only the LLM `observation_summary`, never raw message text, in `observations.content`. `source_ref` is just `msg:<ts>`.
- **Confidence ceiling:** unchanged — `synthesize_traits` caps at 0.55 until human review.
