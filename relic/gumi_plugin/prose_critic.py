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
        r"|in (conclusione|sintesi|definitiva))\b", re.I)),
    ("ai_cliche", re.compile(
        # English first
        r"\b(delve|tapestry|navigate|landscape|realm|testament"
        r"|let'?s (dive|delve) (in|into)"
        r"|embark on a journey|a journey (through|into)"
        r"|in the (realm|world) of"
        # Italian
        r"|nel (mondo|panorama) (di|del|della)"
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
    r"|ti sei mai (chiesto|domandato)|sai (qual è|cosa)|la verità è che)\b", re.I)
_EM_DASH_RE = re.compile(r"\s—\s")

# Score model: start at MAX, subtract a fixed cost per matched violation,
# floor at 0. A lower score means more AI tells. Costs are deliberately coarse
# until calibrated.
_MAX_SCORE = 50
_PHRASE_COST = 6
_STRUCTURE_COST = 5
_EM_DASH_COST = 3
# Default review threshold (advisory): mirrors stop-slop's 35/50 cutoff.
DEFAULT_THRESHOLD = 35


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

        for code, pattern in _BANNED_PHRASES:
            if pattern.search(text):
                violations.append(code)
                score -= _PHRASE_COST

        if _BINARY_CONTRAST_RE.search(text):
            violations.append("binary_contrast")
            score -= _STRUCTURE_COST
        if _RHETORICAL_SETUP_RE.search(text):
            violations.append("rhetorical_setup")
            score -= _STRUCTURE_COST

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
