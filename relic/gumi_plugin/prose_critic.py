"""Prose-quality critic — detects AI writing tells in subject-facing text.

Companion to `OutputCritic` (critic.py). Where `OutputCritic` is a *safety*
guardrail (dependency claims, false embodiment, clinical overreach),
`ProseCritic` is a *style* guardrail: it scores how much the text reads like
generic AI output ("slop") rather than a human voice.

Mechanism is deterministic and inspectable: a banned-phrase list plus
structural detectors feed a bounded score. Adapted from the stop-slop rubric
(github.com/hardikpandya/stop-slop), with Italian equivalents because Gumi's
subject-facing voice is Italian.

Default posture is OBSERVE-ONLY: `review()` returns a score and the matched
violations but keeps `allow=True`, because blocking on prose quality requires
a threshold calibrated on real Italian Gumi output (not yet done). A hard block
is opt-in via `hard_block=True` once a defensible threshold exists.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# --- Phrase-level tells: throat-clearing, vague declaratives, AI clichés. ---
# Each entry: (code, compiled regex). Italian first, English mixed in because
# the model occasionally leaks English filler structures into Italian prose.
_BANNED_PHRASES: list[tuple[str, re.Pattern[str]]] = [
    ("throat_clearing", re.compile(
        # English first
        r"\b(it'?s (important|worth) (to note|noting|remembering)"
        r"|(it is|it's) worth noting"
        r"|in conclusion|in summary|to sum up"
        r"|in today'?s (world|landscape|fast-paced)"
        # Italian
        r"|è importante (notare|ricordare|sottolineare)"
        r"|vale la pena (notare|ricordare|sottolineare)"
        r"|va (notato|detto|ricordato) che"
        r"|emerge chiaramente|possiamo affermare che|resta inteso che"
        r"|spero che questo messaggio ti trovi bene"
        r"|in (conclusione|sintesi|definitiva))\b", re.I)),
    ("ai_cliche", re.compile(
        # English first
        r"\b(delve|tapestry|navigate|landscape|realm|testament"
        r"|let'?s (dive|delve) (in|into)"
        r"|embark on a journey|a journey (through|into)"
        r"|in the (realm|world) of"
        # Italian
        r"|nel (mondo|panorama) (di|del|della)"
        r"|valore aggiunto|senza precedenti|in continua evoluzione"
        r"|a lungo termine|panorama attuale"
        r"|un viaggio (attraverso|nel))\b", re.I)),
    ("hedging_filler", re.compile(
        # English first
        r"\b(in a sense|so to speak|to be honest|honestly|frankly"
        r"|to be fair|that being said|needless to say"
        # Italian
        r"|in un certo senso|per così dire|a dire il vero"
        r"|onestamente|francamente|semplicemente)\b", re.I)),
    ("vague_declarative", re.compile(
        # English first
        r"\b(there are (many|several|various|a number of) (ways|factors|aspects)"
        r"|plays a (key|crucial|vital|pivotal|important) role"
        # Italian
        r"|ci sono (molti|diversi|vari) (modi|fattori|aspetti)"
        r"|gioca un ruolo (fondamentale|cruciale|importante))\b", re.I)),
]

# --- Structural tells: binary contrasts, rhetorical setups, list scaffolding. ---
_BINARY_CONTRAST_RE = re.compile(
    # English first, then Italian
    r"\bnot (only|just|merely)\b.{0,80}\bbut (also|rather)\b"
    r"|\bnon (solo|soltanto|si tratta (solo|soltanto))\b.{0,80}\bma anche\b",
    re.I | re.S)
_RHETORICAL_SETUP_RE = re.compile(
    # English first, then Italian
    r"\b(have you ever (wondered|thought)|do you (know|ever wonder)"
    r"|here'?s the (thing|truth)|the (truth|thing) is"
    r"|ti sei mai (chiesto|domandato)|sai (qual è|cosa)|la verità è che"
    r"|chi (di noi )?non (vorrebbe|desidera|vuole|sogna))\b", re.I)
_EM_DASH_RE = re.compile(r"\s—\s")

# Score model: start at MAX, subtract a fixed cost per matched violation,
# floor at 0. A lower score means more AI tells. Costs are deliberately coarse
# until calibrated.
_MAX_SCORE = 50
_PHRASE_COST = 6
_STRUCTURE_COST = 5
_EM_DASH_COST = 3
# Default review threshold (advisory). Calibrated offline against a gemma
# judge over a generated Italian Gumi-style corpus (scripts/prose_calibration.py):
# n=19, Youden J=0.70 at this cutoff (gemma natural>=50 vs slop<50). Replaces the
# original stop-slop 35/50 default, which left dense Italian slop above the line.
# Still advisory: hard_block is off by default; re-run calibration as corpus grows.
DEFAULT_THRESHOLD = 45


@dataclass(frozen=True)
class ProseVerdict:
    allow: bool
    reason: str
    score: int
    violations: list[str] = field(default_factory=list)


class ProseCritic:
    """Deterministic prose-quality scorer. Pure: no I/O, never raises in review."""

    def __init__(self, threshold: int = DEFAULT_THRESHOLD, hard_block: bool = False) -> None:
        self.threshold = threshold
        self.hard_block = hard_block

    def review(self, text: str) -> ProseVerdict:
        # Defensive coercion: post_llm_call must never raise on unexpected payloads.
        if not isinstance(text, str):
            try:
                text = "" if text is None else str(text)
            except Exception:
                return ProseVerdict(allow=True, reason="empty", score=_MAX_SCORE)
        if not text.strip():
            return ProseVerdict(allow=True, reason="empty", score=_MAX_SCORE)

        violations: list[str] = []
        score = _MAX_SCORE

        # Score by occurrence count (density), not mere presence: dense slop
        # must lose more than a single passing tell. The violations list stays
        # deduplicated (one code per category) for readability.
        for code, pattern in _BANNED_PHRASES:
            hits = len(pattern.findall(text))
            if hits:
                violations.append(code)
                score -= _PHRASE_COST * hits

        binary_hits = len(_BINARY_CONTRAST_RE.findall(text))
        if binary_hits:
            violations.append("binary_contrast")
            score -= _STRUCTURE_COST * binary_hits
        rhetorical_hits = len(_RHETORICAL_SETUP_RE.findall(text))
        if rhetorical_hits:
            violations.append("rhetorical_setup")
            score -= _STRUCTURE_COST * rhetorical_hits

        em_dashes = len(_EM_DASH_RE.findall(text))
        if em_dashes:
            violations.append(f"em_dash_x{em_dashes}")
            score -= _EM_DASH_COST * em_dashes

        score = max(0, score)
        below = score < self.threshold
        # Observe-only unless hard_block is explicitly enabled with a calibrated
        # threshold. Block decisions stay fail-open: allow when in doubt.
        allow = not (self.hard_block and below)
        if not violations:
            reason = "ok"
        elif below:
            reason = "below_threshold"
        else:
            reason = "tells_present"
        return ProseVerdict(allow=allow, reason=reason, score=score, violations=violations)


def suggest_threshold(scores: list[int], percentile: float = 10.0) -> int | None:
    """Suggest a hard-block threshold from a real score distribution.

    Returns the score at the given low percentile (default 10th): blocking
    below it targets the worst ~10% of real output. Returns None when there
    is too little data to be meaningful (<30 samples) — never guess on noise.
    """
    clean = sorted(int(s) for s in scores if isinstance(s, (int, float)))
    if len(clean) < 30:
        return None
    pct = max(0.0, min(100.0, percentile))
    # Nearest-rank percentile.
    rank = max(1, int(round(pct / 100.0 * len(clean))))
    return clean[rank - 1]


def load_calibration_scores(path: object = None) -> list[int]:
    """Load score values from the calibration jsonl. Empty list on any error."""
    try:
        import json

        if path is None:
            from relic.paths import get_relic_home

            path = get_relic_home() / "prose_calibration.jsonl"
        scores: list[int] = []
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    scores.append(int(rec["score"]))
                except Exception:
                    continue
        return scores
    except Exception:
        return []


def log_calibration_sample(
    verdict: "ProseVerdict", text: str, *, decision_type: str = "",
    gemma_score: int | None = None, sink: object = None,
) -> None:
    """Append a numeric-only calibration record to prose_calibration.jsonl.

    PRIVACY: never writes the prose itself nor a hash of it. Only the score,
    violation codes, decision_type, and word count — enough to compute a
    threshold from the real score distribution without retaining content.
    Fail-open: any error is swallowed so calibration logging never blocks
    or breaks delivery.
    """
    try:
        import json
        from datetime import datetime, timezone

        record = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "score": verdict.score,
            "violations": list(verdict.violations),
            "decision_type": decision_type or "",
            "n_words": len(text.split()) if isinstance(text, str) else 0,
            "gemma_score": gemma_score,
        }
        line = json.dumps(record, ensure_ascii=False)
        if sink is not None:
            sink.write(line + "\n")  # injectable for tests
            return
        from relic.paths import get_relic_home

        path = get_relic_home() / "prose_calibration.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass
