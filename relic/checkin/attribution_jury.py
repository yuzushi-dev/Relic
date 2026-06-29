"""Importable cross-family attribution jury (bias-resistant facet attribution).

A single LLM judge with one prompt at low temperature is vulnerable to model
bias, prompt bias, position bias and leniency bias. This jury mitigates all four
with a genuine cross-family panel plus a non-LLM voter:

  LLM panel   THREE distinct free model families on the local Ollama cloud
              endpoint (gemma4 / gpt-oss / minimax), cross-family disagreement
              cancels per-model bias. Each judge votes by FORCED CHOICE ("which
              candidate does the text best evidence, or NONE") instead of yes/no,
              kills leniency/yes-bias, with SAMPLES samples each at temp>0 and
              the candidate list SHUFFLED every call (self-consistency +
              position-bias mitigation), each judge pinned to a prompt template.
  Voter +1    DETERMINISTIC lexical overlap (text tokens vs each facet's
              name+description+spectrum). Immune to any LLM bias; an independent
              vote, not an LLM at all.

Methodology follows the "panel of LLM judges / jury" line of work (Verga et al.,
"Replacing Judges with Juries: Evaluating LLM Generations with a Panel of Diverse
Models", arXiv:2404.18796).

This module is the reusable core shared by the dev validator
(`scripts/dev/validate_attribution_jury.py`) and the passive extractor. It holds
only the importable, side-effect-light pieces (endpoint/key plumbing, the panel
constants, the forced-choice judge, candidate grounding, the lexical voter and
the vote aggregator); the validator keeps its own DB/CLI orchestration.
"""
from __future__ import annotations

import itertools
import json
import os
import re
import threading
import urllib.request
from collections import Counter
from pathlib import Path

# Endpoint. The local daemon (http://localhost:11434/v1) proxies to cloud but is
# a single-account bottleneck: rate-limited for a 40k-call audit. Point at the
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


def tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-zàèéìòù]+", (text or "").lower()) if len(t) > 3 and t not in _STOP}


# --------------------------------------------------------------------------- LLM

def llm_choose(model: str, reply: str, question: str, candidates: list[dict],
               template: int, kind: str = "reply") -> str | None:
    """Forced-choice: return the chosen facet id (or 'NONE'). None on failure.

    kind="reply": text is a subject reply to a check-in question.
    kind="observation": text is an already-extracted observation summary (mnemon
    passive/session obs have no question/reply pair), judge whether the content
    itself evidences the facet.
    """
    none_line = ("- NONE: il testo non porta evidenza su nessuna di queste dimensioni")
    lines = [f'- {c["id"]}: {c["name"]}, {c["description"]}' for c in candidates]
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

def candidates(conn, recorded: str, siblings: list[str], reply: str, facets: dict) -> list[dict]:
    ids = {recorded, *siblings}
    # top lexical matches add real distractors / alternatives
    scored = sorted(
        ((fid, len(tokens(reply) & tokens(f["name"] + " " + f["description"] + " " +
                                          (f["spectrum_low"] or "") + " " + (f["spectrum_high"] or ""))))
         for fid, f in facets.items()),
        key=lambda x: -x[1],
    )
    for fid, sc in scored[:5]:
        if sc > 0:
            ids.add(fid)
    return [dict(id=fid, **{k: facets[fid][k] for k in ("name", "description")}) for fid in ids]


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


def lexical_best(reply: str, candidates: list[dict], facets: dict) -> str:
    rt = tokens(reply)
    best, best_sc = "NONE", 0
    for c in candidates:
        f = facets[c["id"]]
        sc = len(rt & tokens(f["name"] + " " + f["description"] + " " +
                             (f["spectrum_low"] or "") + " " + (f["spectrum_high"] or "")))
        if sc > best_sc:
            best, best_sc = c["id"], sc
    return best


def aggregate(recorded: str, votes: list[str], by_judge: dict[str, list[str]]) -> dict:
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
