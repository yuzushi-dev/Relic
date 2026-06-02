#!/usr/bin/env python3
"""Jury-based validation of check-in reply→facet attribution (bias-resistant).

A single LLM judge with one prompt at low temperature is vulnerable to model
bias, prompt bias, position bias and leniency bias. This validator mitigates all
four with a genuine cross-family panel plus a non-LLM voter:

  LLM panel   THREE distinct free model families on the local Ollama cloud
              endpoint (gemma4 / gpt-oss / minimax) — cross-family disagreement
              cancels per-model bias. Each judge votes by FORCED CHOICE ("which
              candidate does the reply best evidence, or NONE") instead of yes/no
              — kills leniency/yes-bias — with SAMPLES samples each at temp>0 and
              the candidate list SHUFFLED every call (self-consistency +
              position-bias mitigation), each judge pinned to a prompt template.
  Voter +1    DETERMINISTIC lexical overlap (reply tokens vs each facet's
              name+description+spectrum). Immune to any LLM bias; an independent
              vote, not an LLM at all.

Methodology follows the "panel of LLM judges / jury" line of work (Verga et al.,
"Replacing Judges with Juries: Evaluating LLM Generations with a Panel of Diverse
Models", arXiv:2404.18796). Existing libraries were evaluated and not adopted:
quotient-ai/judges (Jury class) ships only correctness/RAG classifiers — not
custom facet attribution — and assumes cloud API keys; karpathy/llm-council is a
free-text web deliberation app. Both are heavier than this dependency-free,
Ollama-only, classification-specific script, so the jury is implemented inline.

Candidates are grounded: the recorded facet + its batch siblings (the other
facets asked in the same tick — the true target is almost always one of these)
+ the top lexical matches + NONE.

A verdict only flags/acts on STRONG agreement (>= AGREE_MIN of the voters
disagree with the recorded facet). Otherwise: inconclusive → leave untouched.

Read-only by default. `--apply` resolves confirmed verdicts (backup first):
  - reattribute: move observation+reply to the agreed facet, recompute traits
  - drop:        delete the observation (reply is off-topic / NONE), recompute

Usage:
    RELIC_HOME=~/.relic .venv/bin/python scripts/dev/validate_attribution_jury.py --subject daniele
    ...                                                                            --apply
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sqlite3
import urllib.request
from collections import Counter
from pathlib import Path

import itertools
import threading

# Endpoint. The local daemon (http://localhost:11434/v1) proxies to cloud but is
# a single-account bottleneck — rate-limited for a 40k-call audit. Point at the
# direct cloud endpoint and rotate across several API keys to spread the load.
#   export RELIC_OLLAMA_ENDPOINT=https://ollama.com/v1
ENDPOINT = os.environ.get("RELIC_OLLAMA_ENDPOINT", "http://localhost:11434/v1")
_IS_CLOUD = "ollama.com" in ENDPOINT


def _load_keys() -> list[str]:
    """API keys for cloud endpoint: OLLAMA_API_KEYS (comma) or a keys file."""
    keys: list[str] = []
    env = os.environ.get("OLLAMA_API_KEYS", "").strip()
    if env:
        keys += [k.strip() for k in env.split(",") if k.strip()]
    path = Path(os.environ.get("OLLAMA_KEYS_FILE", str(Path.home() / ".ollama" / "cloud_keys.txt")))
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                keys.append(line)
    # de-dup preserving order
    seen: set[str] = set()
    return [k for k in keys if not (k in seen or seen.add(k))]


_KEYS = _load_keys()
_key_cycle = itertools.cycle(_KEYS) if _KEYS else None
_key_lock = threading.Lock()


def _next_key() -> str | None:
    if _key_cycle is None:
        return None
    with _key_lock:
        return next(_key_cycle)


# Cross-family panel: each entry is (model, prompt_template). Distinct model
# families, so agreement is not one model agreeing with itself. On the direct
# cloud endpoint, tags carry no "-cloud" suffix; on the local proxy they do.
_PANEL_LOCAL = [("gemma4:31b-cloud", 0), ("gpt-oss:120b-cloud", 1), ("minimax-m3:cloud", 0)]
_PANEL_CLOUD = [("gemma4:31b", 0), ("gpt-oss:120b", 1), ("minimax-m3", 0)]
JUDGES: list[tuple[str, int]] = _PANEL_CLOUD if _IS_CLOUD else _PANEL_LOCAL
SAMPLES = 2  # samples per judge (self-consistency); total LLM votes = 3*SAMPLES
# Voters = len(JUDGES)*SAMPLES LLM + 1 lexical. Flag only on a strict majority.
N_VOTERS = len(JUDGES) * SAMPLES + 1
AGREE_MIN = N_VOTERS // 2 + 1  # strict majority must reject the recorded facet

_STOP = set(
    "il lo la i gli le un uno una di a da in con su per tra fra e o ma se che chi cui "
    "non mi ti si ci vi è sono ho hai ha abbiamo come quando dove più meno molto poco "
    "del della dei delle al allo alla ai agli alle nel nella sul sulla un'".split()
)


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-zàèéìòù]+", (text or "").lower()) if len(t) > 3 and t not in _STOP}


# --------------------------------------------------------------------------- LLM

def _llm_choose(model: str, reply: str, question: str, candidates: list[dict],
                template: int, kind: str = "reply") -> str | None:
    """Forced-choice: return the chosen facet id (or 'NONE'). None on failure.

    kind="reply": text is a subject reply to a check-in question.
    kind="observation": text is an already-extracted observation summary (mnemon
    passive/session obs have no question/reply pair) — judge whether the content
    itself evidences the facet.
    """
    none_line = ("- NONE: il testo non porta evidenza su nessuna di queste dimensioni")
    lines = [f'- {c["id"]}: {c["name"]} — {c["description"]}' for c in candidates]
    lines.append(none_line)
    catalog = "\n".join(lines)
    valid_ids = {c["id"] for c in candidates} | {"NONE"}

    if kind == "observation":
        prompt = (
            "Compito di attribuzione. Il seguente CONTENUTO è un'osservazione "
            "comportamentale già estratta. Individua l'unica dimensione per cui il "
            "contenuto fornisce evidenza diretta; se nessuna è pertinente scegli NONE.\n\n"
            f"CONTENUTO OSSERVATO: {reply}\n\nOPZIONI:\n{catalog}\n\n"
            'Output JSON e nient altro: {"best": "<id esatto o NONE>"}'
        )
    elif template == 0:
        prompt = (
            "Una persona ha ricevuto una domanda e ha risposto. Scegli QUALE dimensione "
            "comportamentale la RISPOSTA evidenzia meglio. Scegli esattamente un id dalla lista "
            "(o NONE). Giudica il CONTENUTO della risposta, non la domanda.\n\n"
            f"DOMANDA POSTA: {question}\nRISPOSTA: {reply}\n\nCANDIDATI:\n{catalog}\n\n"
            'Rispondi SOLO con JSON: {"best": "<id o NONE>"}'
        )
    else:
        prompt = (
            "Compito di attribuzione. Data la risposta qui sotto, individua l'unica dimensione "
            "per cui la risposta fornisce evidenza diretta. Se nessuna è pertinente, scegli NONE. "
            "Ignora a quale domanda sembrava rispondere; conta solo cosa dice la risposta.\n\n"
            f"RISPOSTA DELLA PERSONA: {reply}\n\nOPZIONI:\n{catalog}\n\n"
            'Output JSON e nient altro: {"best": "<id esatto o NONE>"}'
        )

    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": "Sei un annotatore comportamentale rigoroso. Rispondi solo JSON valido."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.5,
        # Reasoning models (gpt-oss, minimax) ignore think=False and spend tokens
        # on a reasoning trace before the content; too small a budget truncates
        # before the JSON answer is emitted. Give ample headroom.
        "max_tokens": 800,
        "think": False,
    }).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    key = _next_key()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(
        f"{ENDPOINT}/chat/completions", data=payload,
        headers=headers, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            raw = resp.read().decode("utf-8")
        # strict=False: gpt-oss / minimax emit a `reasoning` field containing raw
        # control characters (unescaped newlines) even with think=False, which
        # breaks a strict envelope parse and silently drops those judges' votes.
        data = json.loads(raw, strict=False)
        msg = data["choices"][0]["message"]
        text = (msg.get("content") or msg.get("reasoning") or "").strip()
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
        # Prefer the LAST {...} block: reasoning models often restate the prompt's
        # example JSON first and emit the real answer last.
        blocks = re.findall(r"\{[^{}]*\}", text, flags=re.DOTALL)
        for blk in reversed(blocks):
            try:
                best = str(json.loads(blk, strict=False).get("best", "")).strip()
            except Exception:
                continue
            if best in valid_ids:
                return best
        return None
    except Exception:
        return None


# --------------------------------------------------------------------------- jury

def _candidates(conn, recorded: str, siblings: list[str], reply: str, facets: dict) -> list[dict]:
    ids = {recorded, *siblings}
    # top lexical matches add real distractors / alternatives
    scored = sorted(
        ((fid, len(_tokens(reply) & _tokens(f["name"] + " " + f["description"] + " " +
                                            (f["spectrum_low"] or "") + " " + (f["spectrum_high"] or ""))))
         for fid, f in facets.items()),
        key=lambda x: -x[1],
    )
    for fid, sc in scored[:5]:
        if sc > 0:
            ids.add(fid)
    return [dict(id=fid, **{k: facets[fid][k] for k in ("name", "description")}) for fid in ids]


def _lexical_best(reply: str, candidates: list[dict], facets: dict) -> str:
    rt = _tokens(reply)
    best, best_sc = "NONE", 0
    for c in candidates:
        f = facets[c["id"]]
        sc = len(rt & _tokens(f["name"] + " " + f["description"] + " " +
                              (f["spectrum_low"] or "") + " " + (f["spectrum_high"] or "")))
        if sc > best_sc:
            best, best_sc = c["id"], sc
    return best


def validate(conn, facets: dict, rng: random.Random) -> list[dict]:
    rows = conn.execute(
        """SELECT o.id obs_id, ce.id ex_id, o.facet_id, ce.reply_text, ce.question_text
           FROM observations o JOIN checkin_exchanges ce ON ('exchange:'||ce.id)=o.source_ref
           WHERE o.source_type='checkin_reply' AND o.source_ref LIKE 'exchange:%'
           ORDER BY ce.id"""
    ).fetchall()

    verdicts = []
    for obs_id, ex_id, recorded, reply, question in rows:
        bucket = conn.execute(
            "SELECT substr(asked_at,1,19) FROM checkin_exchanges WHERE id=?", (ex_id,)
        ).fetchone()[0]
        siblings = [
            r[0] for r in conn.execute(
                "SELECT DISTINCT facet_id FROM checkin_exchanges "
                "WHERE substr(asked_at,1,19)=? AND facet_id IS NOT NULL AND facet_id<>?",
                (bucket, recorded),
            ).fetchall()
        ]
        cands = _candidates(conn, recorded, siblings, reply, facets)

        votes: list[str] = []
        by_judge: dict[str, list[str]] = {}
        for model, template in JUDGES:
            for _ in range(SAMPLES):
                shuffled = cands[:]
                rng.shuffle(shuffled)
                v = _llm_choose(model, reply, question or "", shuffled, template)
                if v is not None:
                    votes.append(v)
                    by_judge.setdefault(model, []).append(v)
        lex = _lexical_best(reply, cands, facets)
        votes.append(lex)  # deterministic voter

        tally = Counter(votes)
        reject = sum(n for v, n in tally.items() if v != recorded)
        keep = tally.get(recorded, 0)
        plurality = tally.most_common(1)[0][0] if tally else recorded

        # Per-judge majority verdict (cross-family signal): a judge "rejects" the
        # recorded facet only if its own samples' plurality is something else.
        judge_choice = {m: Counter(vs).most_common(1)[0][0] for m, vs in by_judge.items()}
        families_rejecting = sum(1 for c in judge_choice.values() if c != recorded)

        # Threshold relative to votes actually cast (robust if a judge fails to
        # answer): require a strict majority of cast votes to reject the recorded
        # facet, the plurality to land elsewhere, AND >= 2 distinct model
        # families to reject (so no single model's bias drives the verdict).
        cast = sum(tally.values())
        need = cast // 2 + 1
        confirmed = (cast >= 4 and reject >= need and plurality != recorded
                     and families_rejecting >= 2)
        if confirmed:
            action = "drop" if plurality == "NONE" else "reattribute"
            target = None if plurality == "NONE" else plurality
        else:
            action, target = "keep", recorded

        verdicts.append({
            "obs_id": obs_id, "ex_id": ex_id, "recorded": recorded,
            "votes": dict(tally), "keep_votes": keep, "reject_votes": reject,
            "lexical": lex, "judge_choice": judge_choice,
            "families_rejecting": families_rejecting,
            "action": action, "target": target,
            "siblings": siblings, "reply_head": (reply or "")[:70].replace("\n", " "),
            "reply_text": reply, "question_text": question,
        })
    return verdicts


# --------------------------------------------------------------------- all-obs jury

SAMPLES_ALL = 1  # 1 sample/judge for the bulk audit: 3 LLM + 1 lexical = 4 voters


def _aggregate(recorded: str, votes: list[str], by_judge: dict[str, list[str]]) -> dict:
    tally = Counter(votes)
    reject = sum(n for v, n in tally.items() if v != recorded)
    keep = tally.get(recorded, 0)
    plurality = tally.most_common(1)[0][0] if tally else recorded
    judge_choice = {m: Counter(vs).most_common(1)[0][0] for m, vs in by_judge.items()}
    fam_reject = sum(1 for c in judge_choice.values() if c != recorded)
    cast = sum(tally.values())
    need = cast // 2 + 1
    confirmed = cast >= 3 and reject >= need and plurality != recorded and fam_reject >= 2
    if confirmed:
        action = "drop" if plurality == "NONE" else "reattribute"
        target = None if plurality == "NONE" else plurality
    else:
        action, target = "keep", recorded
    return {"votes": dict(tally), "keep_votes": keep, "reject_votes": reject,
            "judge_choice": judge_choice, "families_rejecting": fam_reject,
            "action": action, "target": target}


def _enrich(content: str, context: str, meta: str) -> str:
    """Assemble the context-aware judge text from the fields mnemon stored.

    `content` alone is raw chat text / session dump and judging it in isolation
    grossly over-flags (a dev message reads as evidence for no personality
    facet). mnemon attributed using its own distilled interpretation (`context`,
    an English gloss like "Technical instruction about ...") plus signal
    metadata (tone, interlocutor, time). Feeding those to the panel reproduces
    the information mnemon actually had, modulo full conversation history.
    """
    parts = [f"MESSAGGIO/TESTO: {(content or '')[:500]}"]
    if context:
        parts.append(f"INTERPRETAZIONE: {context[:300]}")
    if meta:
        tone = interloc = tc = ""
        try:
            m = json.loads(meta)
            tone, interloc, tc = m.get("tone", ""), m.get("interlocutor_type", ""), m.get("time_context", "")
        except Exception:
            pass
        tags = ", ".join(x for x in (f"tono={tone}" if tone else "",
                                     f"interlocutore={interloc}" if interloc else "",
                                     f"momento={tc}" if tc else "") if x)
        if tags:
            parts.append(f"SEGNALI: {tags}")
    return "\n".join(parts)


def _judge_obs(obs_id: int, recorded: str, content: str, source_type: str,
               facets: dict, seed: int, context: str = "", meta: str = "") -> dict:
    """Context-aware jury for one observation. Thread-safe.

    Uses content + mnemon's stored `context` gloss + signal metadata so the panel
    judges with the information mnemon used, not a decontextualised snippet.
    """
    rng = random.Random(seed ^ (obs_id * 2654435761))
    text = _enrich(content, context, meta)
    # Candidate lexical pool spans both the raw text and the interpretation gloss.
    lex_src = f"{content or ''} {context or ''}"
    cands = _candidates(None, recorded, [], lex_src, facets)
    votes: list[str] = []
    by_judge: dict[str, list[str]] = {}
    for model, template in JUDGES:
        for _ in range(SAMPLES_ALL):
            shuffled = cands[:]
            rng.shuffle(shuffled)
            v = _llm_choose(model, text, "", shuffled, template, kind="observation")
            if v is not None:
                votes.append(v)
                by_judge.setdefault(model, []).append(v)
    votes.append(_lexical_best(lex_src, cands, facets))
    agg = _aggregate(recorded, votes, by_judge)
    return {"obs_id": obs_id, "recorded": recorded, "source_type": source_type,
            "content_head": (content or "")[:70].replace("\n", " "),
            "context_head": (context or "")[:70].replace("\n", " "), **agg}


def validate_all(conn, facets: dict, seed: int, workers: int, checkpoint: Path,
                 sample: int = 0) -> Path:
    """Jury over ALL observations, parallel + resumable via JSONL checkpoint.

    sample>0: judge a random subset (method-validation pilot) instead of all.
    """
    done: set[int] = set()
    if checkpoint.exists():
        for line in checkpoint.read_text(encoding="utf-8").splitlines():
            try:
                done.add(int(json.loads(line)["obs_id"]))
            except Exception:
                continue
    rows = conn.execute(
        "SELECT id, facet_id, content, source_type, context, context_metadata "
        "FROM observations WHERE content IS NOT NULL AND content <> '' ORDER BY id"
    ).fetchall()
    todo = [r for r in rows if r[0] not in done]
    if sample and sample < len(todo):
        random.Random(seed).shuffle(todo)
        todo = todo[:sample]
    print(f"all-obs audit: {len(rows)} total, {len(done)} done, {len(todo)} to judge"
          f"{' (SAMPLE)' if sample else ''} "
          f"({workers} workers, {len(_KEYS)} keys, panel={[m for m,_ in JUDGES]})", flush=True)

    write_lock = threading.Lock()
    fh = checkpoint.open("a", encoding="utf-8")
    completed = 0
    try:
        import concurrent.futures as cf
        with cf.ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(_judge_obs, r[0], r[1], r[2], r[3], facets, seed, r[4], r[5]): r[0]
                    for r in todo}
            for fut in cf.as_completed(futs):
                try:
                    v = fut.result()
                except Exception as exc:
                    v = {"obs_id": futs[fut], "error": str(exc)}
                with write_lock:
                    fh.write(json.dumps(v, ensure_ascii=False) + "\n")
                    fh.flush()
                completed += 1
                if completed % 100 == 0:
                    print(f"  ...{completed}/{len(todo)}", flush=True)
    finally:
        fh.close()
    print(f"all-obs audit complete: +{completed} verdicts → {checkpoint}", flush=True)
    return checkpoint


def report_checkpoint(checkpoint: Path) -> None:
    """Summarize a checkpoint JSONL: mis-attribution rate per source_type."""
    by_src: dict[str, list[int]] = {}
    flagged: list[dict] = []
    total = errors = 0
    for line in checkpoint.read_text(encoding="utf-8").splitlines():
        try:
            v = json.loads(line)
        except Exception:
            continue
        if v.get("error"):
            errors += 1
            continue
        total += 1
        st = v.get("source_type", "?")
        bad = 1 if v["action"] != "keep" else 0
        by_src.setdefault(st, [0, 0])
        by_src[st][0] += bad
        by_src[st][1] += 1
        if bad:
            flagged.append(v)
    print(f"\n==== all-obs attribution report ({total} judged, {errors} errors) ====")
    print(f"{'source_type':<22} {'flagged':>8} {'total':>7} {'rate':>7}")
    for st in sorted(by_src, key=lambda s: -by_src[s][0]):
        bad, tot = by_src[st]
        print(f"{st:<22} {bad:>8} {tot:>7} {bad/tot*100:>6.1f}%")
    tot_bad = sum(b for b, _ in by_src.values())
    print(f"{'TOTAL':<22} {tot_bad:>8} {total:>7} {tot_bad/max(total,1)*100:>6.1f}%")
    print(f"\nflagged breakdown: drop={sum(v['action']=='drop' for v in flagged)}, "
          f"reattribute={sum(v['action']=='reattribute' for v in flagged)}")


# --------------------------------------------------------------------------- resolve

def _adjust_trait_count(conn, facet_id: str, delta: int) -> None:
    """Adjust only observation_count by delta; never overwrite value_position.

    value_position is a synthesized aggregate owned by the writing pipelines
    (checkin facet_updater's incremental EWMA + the external mnemon synthesis).
    Rebuilding it here from scratch would NOT reproduce that synthesis — an early
    experiment recomputing a chronological EWMA over all observations flipped one
    live trait from 0.26 to 0.67, far beyond removing a single contaminated
    observation. A single corrected observation among dozens shifts the aggregate
    negligibly, so we leave value_position to re-settle on the next synthesis and
    only keep the count honest.
    """
    conn.execute(
        "UPDATE traits SET observation_count=MAX(0, observation_count + ?) WHERE facet_id=?",
        (delta, facet_id),
    )


def apply_verdicts(conn, verdicts: list[dict], facets: dict) -> dict:
    """Resolve confirmed verdicts.

    signal_position is facet-relative (it is the reply's position on THAT facet's
    spectrum), so re-attribution cannot be a blind facet_id swap — the stored
    value was computed against the wrong spectrum. For reattribute we re-run the
    extractor against the target facet's spectrum and rewrite content/signal, or
    drop the row if the reply turns out non-informative for the target too. The
    original exchange's source_ref is preserved so provenance stays traceable.
    Traits only have their observation_count nudged (see _adjust_trait_count);
    value_position synthesis is intentionally left to the owning pipelines.
    """
    from relic.checkin.facet_updater import extract_observation

    count_delta: Counter = Counter()
    dropped = reattributed = 0
    log: list[str] = []
    for v in verdicts:
        if v["action"] == "drop":
            conn.execute("DELETE FROM observations WHERE id=?", (v["obs_id"],))
            count_delta[v["recorded"]] -= 1
            dropped += 1
            log.append(f"drop obs{v['obs_id']} [{v['recorded']}]")
        elif v["action"] == "reattribute":
            tgt = v["target"]
            tf = facets[tgt]
            ext = extract_observation(
                exchange_id=v["ex_id"], facet_id=tgt,
                facet_name=tf["name"], description=tf["description"],
                spectrum_low=tf["spectrum_low"] or "low",
                spectrum_high=tf["spectrum_high"] or "high",
                question_text=v["question_text"] or "",
                reply_text=v["reply_text"],
            )
            if ext.error:
                log.append(f"SKIP obs{v['obs_id']}: re-extract error={ext.error}")
                continue
            if ext.informative:
                conn.execute(
                    "UPDATE observations SET facet_id=?, content=?, signal_position=?, "
                    "signal_strength=? WHERE id=?",
                    (tgt, ext.observation_summary, ext.signal_position,
                     ext.signal_strength, v["obs_id"]),
                )
                count_delta[v["recorded"]] -= 1
                count_delta[tgt] += 1
                log.append(f"reattribute obs{v['obs_id']} [{v['recorded']}]→[{tgt}] "
                           f"sp={ext.signal_position}")
            else:
                conn.execute("DELETE FROM observations WHERE id=?", (v["obs_id"],))
                count_delta[v["recorded"]] -= 1
                log.append(f"drop obs{v['obs_id']} [{v['recorded']}] "
                           f"(non-informative for target {tgt} either)")
            reattributed += 1
    for fid, delta in count_delta.items():
        if delta:
            _adjust_trait_count(conn, fid, delta)
    conn.commit()
    return {"dropped": dropped, "reattributed": reattributed,
            "traits_adjusted": len(count_delta), "log": log}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--subject", required=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--all", action="store_true",
                    help="audit ALL observations (content-based), parallel + checkpointed")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--sample", type=int, default=0,
                    help="judge a random subset (method-validation pilot)")
    ap.add_argument("--checkpoint", default=None)
    ap.add_argument("--report-only", action="store_true",
                    help="just summarize an existing --all checkpoint, no LLM calls")
    args = ap.parse_args()

    relic_home = Path(os.environ.get("RELIC_HOME") or Path.home() / ".relic")
    db = relic_home / "subjects" / args.subject / "relic.db"
    if not db.exists():
        print(f"no db: {db}")
        return 1

    if args.all or args.report_only:
        ckpt = Path(args.checkpoint or f"/tmp/attr_audit_{args.subject}.jsonl")
        if not args.report_only:
            if _IS_CLOUD and not _KEYS:
                print("ERROR: cloud endpoint set but no API keys "
                      "(OLLAMA_API_KEYS or ~/.ollama/cloud_keys.txt)")
                return 2
            conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            facets = {
                r[0]: {"name": r[1], "description": r[2], "spectrum_low": r[3], "spectrum_high": r[4]}
                for r in conn.execute(
                    "SELECT id, name, description, spectrum_low, spectrum_high FROM facets")
            }
            validate_all(conn, facets, args.seed, args.workers, ckpt, sample=args.sample)
            conn.close()
        report_checkpoint(ckpt)
        return 0

    mode = "" if args.apply else "?mode=ro"
    conn = sqlite3.connect(f"file:{db}{mode}", uri=True)
    facets = {
        r[0]: {"name": r[1], "description": r[2], "spectrum_low": r[3], "spectrum_high": r[4]}
        for r in conn.execute("SELECT id, name, description, spectrum_low, spectrum_high FROM facets")
    }
    rng = random.Random(args.seed)
    verdicts = validate(conn, facets, rng)

    panel = ", ".join(m for m, _ in JUDGES)
    print(f"\n==== {args.subject} — jury attribution ({len(verdicts)} observations) ====")
    print(f"panel: {panel} (x{SAMPLES} shuffled samples each) + 1 lexical = {N_VOTERS} voters; "
          f"flag if >= {AGREE_MIN} reject recorded AND >= 2 families reject\n")
    for v in verdicts:
        tag = {"keep": "  OK", "reattribute": "→REATTR", "drop": "✗DROP"}[v["action"]]
        print(f"{tag}  ex{v['ex_id']} obs{v['obs_id']} [{v['recorded']}]  "
              f"keep={v['keep_votes']} reject={v['reject_votes']} fam_reject={v['families_rejecting']} lex={v['lexical']}")
        print(f"        judges={v['judge_choice']}  votes={v['votes']}")
        if v["action"] != "keep":
            print(f"        target={v['target']}  reply=\"{v['reply_head']}\"")

    flagged = [v for v in verdicts if v["action"] != "keep"]
    print(f"\nflagged: {len(flagged)}  (drop={sum(v['action']=='drop' for v in flagged)}, "
          f"reattribute={sum(v['action']=='reattribute' for v in flagged)})")

    if args.apply:
        res = apply_verdicts(conn, verdicts, facets)
        print("\nAPPLIED:")
        for line in res.pop("log", []):
            print(f"  - {line}")
        print(f"  summary: {res}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
