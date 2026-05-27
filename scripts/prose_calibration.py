"""Offline prose-threshold calibration via Ollama (gemma4:31b-cloud).

Real delivered text is never persisted (privacy gate keeps only hashes), so
the ProseCritic threshold cannot be tuned on real output. This script instead:

  1. Generates an Italian Gumi-style corpus with gemma: two intended pools —
     "natural" (human voice) and "slop" (AI tells).
  2. Has gemma blindly judge each message with a prose_score 0-100 (higher =
     more human/natural).
  3. Scores every message with the deterministic ProseCritic regex scorer.
  4. Finds the ProseCritic threshold that best separates gemma-natural from
     gemma-slop (Youden's J), reports correlation and per-violation frequency.
  5. Writes calibration_report.json.

Privacy: the corpus is synthetic (gemma-generated), so no real subject text is
involved. Output report contains only scores/stats, never delivered prose.

Usage:
    python scripts/prose_calibration.py --n 60 --output calibration_report.json
"""
from __future__ import annotations

import argparse
import json
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from relic.gumi_plugin.prose_critic import ProseCritic

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "gemma4:31b-cloud"
TEMPERATURE = 0.9  # high for corpus diversity

_GEN_NATURAL = (
    "Scrivi {k} brevi messaggi in italiano, come li manderebbe un amico via chat: "
    "diretti, concreti, con voce umana e naturale. Niente cliché, niente frasi "
    "fatte, niente tono da assistente AI. Un messaggio per riga, nessuna numerazione."
)
_GEN_SLOP = (
    "Scrivi {k} brevi messaggi in italiano pieni di tipici tell da testo generato "
    "da AI: aperture cerimoniose, frasi fatte, contrasti binari (non solo... ma "
    "anche), domande retoriche, espressioni vaghe. Un messaggio per riga, nessuna "
    "numerazione."
)
_JUDGE = (
    "Valuta quanto questo messaggio suona naturale e umano (NON generato da AI). "
    "Rispondi SOLO con un numero intero da 0 a 100, dove 100 = voce umana "
    "perfettamente naturale e 0 = chiaramente testo AI pieno di cliché.\n\n"
    "Messaggio:\n{msg}\n\nNumero:"
)


def _ollama(prompt: str, *, temperature: float) -> str:
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature},
    }
    data = json.dumps(payload).encode("utf-8")
    last_error: Exception | None = None
    for attempt in range(5):
        req = urllib.request.Request(
            OLLAMA_URL, data=data, headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                body = json.load(resp)
            content = str(body.get("response", "")).strip()
            if content:
                return content
            last_error = RuntimeError("empty response")
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
        backoff = 5 * (attempt + 1)
        print(f"  retry {attempt + 1}/5 after {backoff}s ({last_error})", flush=True)
        time.sleep(backoff)
    raise RuntimeError(f"ollama failed after retries: {last_error}")


def _split_messages(raw: str) -> list[str]:
    out: list[str] = []
    for line in raw.splitlines():
        s = re.sub(r"^\s*[-*\d.)\]]+\s*", "", line).strip()
        if len(s.split()) >= 3:
            out.append(s)
    return out


def _judge_score(msg: str) -> int | None:
    raw = _ollama(_JUDGE.format(msg=msg), temperature=0.0)
    m = re.search(r"\d{1,3}", raw)
    if not m:
        return None
    return max(0, min(100, int(m.group())))


def build_corpus(n: int) -> list[dict]:
    half = max(1, n // 2)
    natural = _split_messages(_ollama(_GEN_NATURAL.format(k=half), temperature=TEMPERATURE))
    slop = _split_messages(_ollama(_GEN_SLOP.format(k=half), temperature=TEMPERATURE))
    corpus = [{"text": t, "intended": "natural"} for t in natural]
    corpus += [{"text": t, "intended": "slop"} for t in slop]
    return corpus


def evaluate(corpus: list[dict]) -> dict:
    critic = ProseCritic()
    rows: list[dict] = []
    for item in corpus:
        v = critic.review(item["text"])
        gemma = _judge_score(item["text"])
        rows.append({
            "intended": item["intended"],
            "regex_score": v.score,
            "violations": v.violations,
            "gemma_score": gemma,
        })
        print(f"  regex={v.score:>2} gemma={gemma} intended={item['intended']}", flush=True)
    return {"rows": rows}


def _best_threshold(rows: list[dict], gemma_cut: int = 50) -> dict:
    """Find the ProseCritic regex threshold maximizing Youden's J against gemma.

    A message is 'bad' when gemma_score < gemma_cut. We pick the regex
    threshold T such that blocking (regex_score < T) best separates bad/good.
    """
    labeled = [r for r in rows if r["gemma_score"] is not None]
    bad = [r for r in labeled if r["gemma_score"] < gemma_cut]
    good = [r for r in labeled if r["gemma_score"] >= gemma_cut]
    if not bad or not good:
        return {"threshold": None, "reason": "insufficient_label_separation",
                "n_bad": len(bad), "n_good": len(good)}
    best_t, best_j = None, -1.0
    for t in range(0, 51):
        tpr = sum(1 for r in bad if r["regex_score"] < t) / len(bad)
        fpr = sum(1 for r in good if r["regex_score"] < t) / len(good)
        j = tpr - fpr
        if j > best_j:
            best_j, best_t = j, t
    return {"threshold": best_t, "youden_j": round(best_j, 3),
            "n_bad": len(bad), "n_good": len(good), "gemma_cut": gemma_cut}


def _violation_freq(rows: list[dict]) -> dict[str, int]:
    freq: dict[str, int] = {}
    for r in rows:
        for v in r["violations"]:
            key = re.sub(r"_x\d+$", "", v)  # collapse em_dash_x3 → em_dash
            freq[key] = freq.get(key, 0) + 1
    return dict(sorted(freq.items(), key=lambda kv: -kv[1]))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=60, help="approx corpus size")
    ap.add_argument("--output", type=Path, default=Path("calibration_report.json"))
    args = ap.parse_args()

    print(f"[calibration] generating corpus (~{args.n}) via {MODEL}", flush=True)
    corpus = build_corpus(args.n)
    print(f"[calibration] {len(corpus)} messages; judging + scoring", flush=True)
    ev = evaluate(corpus)
    rows = ev["rows"]

    report = {
        "report_id": "prose_calibration_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model": MODEL,
        "n_messages": len(rows),
        "suggested_threshold": _best_threshold(rows),
        "violation_frequency": _violation_freq(rows),
        "rows": rows,
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    st = report["suggested_threshold"]
    print(f"[calibration] done → {args.output}", flush=True)
    print(f"[calibration] suggested DEFAULT_THRESHOLD = {st.get('threshold')} "
          f"(Youden J={st.get('youden_j')})", flush=True)


if __name__ == "__main__":
    main()
