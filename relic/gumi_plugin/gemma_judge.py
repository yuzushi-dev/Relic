"""Gemma prose-quality judge (Ollama Cloud) for the delivery path.

The deterministic ProseCritic regex has ~33% recall on diverse Italian slop
(measured via gemma calibration). This module adds an LLM judge that scores how
human/natural a message reads (0-100), for the non-interactive cron delivery
path where a few seconds of latency is acceptable.

Constraints:
- Synchronous but timeout-bounded; fail-open (None) on any error/timeout so it
  never blocks delivery on the judge itself.
- In-process on live text only, nothing is persisted (privacy gate still owns
  the delivered text). The judge returns a number, never stores prose.
- Opt-in: callers gate on env (see checkin_media_dispatcher).
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "gemma4:31b-cloud"

# Shared with scripts/prose_calibration.py: keep the rubric identical so the
# runtime judge and the offline calibration speak the same scale.
JUDGE_PROMPT = (
    "Valuta quanto questo messaggio suona naturale e umano (NON generato da AI). "
    "Rispondi SOLO con un numero intero da 0 a 100, dove 100 = voce umana "
    "perfettamente naturale e 0 = chiaramente testo AI pieno di cliché.\n\n"
    "Messaggio:\n{msg}\n\nNumero:"
)


def judge_score(text: str, *, timeout: int = 20) -> int | None:
    """Return gemma's 0-100 human-naturalness score, or None on any failure.

    No retries: this sits on the delivery path, so a single bounded attempt then
    fail-open. Higher = more natural; lower = more AI slop.
    """
    if not isinstance(text, str) or not text.strip():
        return None
    payload = {
        "model": MODEL,
        "prompt": JUDGE_PROMPT.format(msg=text),
        "stream": False,
        "options": {"temperature": 0.0},
    }
    data = json.dumps(payload).encode("utf-8")
    try:
        req = urllib.request.Request(
            OLLAMA_URL, data=data, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.load(resp)
        content = str(body.get("response", ""))
        m = re.search(r"\d{1,3}", content)
        if not m:
            return None
        return max(0, min(100, int(m.group())))
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None
