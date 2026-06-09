"""Topic gap scorer: selects which facet to explore next via check-in.

Formula (from gumi_topic_gap_score.py, adapted for subject_baseline.json + relic.db):
    TGS = 0.35*unknownness + 0.25*impact + 0.20*timeliness
          - 0.20*intrusion - 0.15*asked_recently

Returns JSON with status: ask_now | not_due | no_candidate | disabled
"""
from __future__ import annotations

import json
import random
import re
import sqlite3

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

# Strip parenthetical clinical scale references: matches single scales (ECR-R, SDT)
# and combined multi-scale refs like (ECR-R, DERS) or (Schwartz, McAdams).
SCALE_REF_RE = re.compile(r"\s*\([A-Z][A-Za-z0-9\-]*(?:,\s*[A-Z][A-Za-z0-9\-]*)*\)")


def clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


# Confidence string → float (shared with style_hints)
CONFIDENCE_LEVEL_MAP = {
    "high":        0.80,
    "medium":      0.50,
    "low":         0.25,
    "low_initial": 0.10,
}

# Sensitivity → base intrusion (overridden by facets.intrusion_base from db)
_SENSITIVITY_INTRUSION = {"bassa": 0.25, "media": 0.45, "alta": 0.65}

# Impact by category (base_impact when no db data available)
_CATEGORY_IMPACT = {
    "relational":    0.85,
    "emotional":     0.82,
    "cognitive":     0.78,
    "meta_cognition":0.76,
    "values":        0.74,
    "communication": 0.70,
    "temporal":      0.65,
    "aesthetic":     0.55,
    "language":      0.50,
}

# Facets seeded from subject_baseline.json: merged with relic.db traits
# Psychological big-five + interaction from bootstrap map to db facet IDs
_BASELINE_TO_DB: dict[str, str] = {
    "agreeableness":               "relational.loyalty_pattern",
    "attachment_anxiety":          "relational.attachment_anxiety",
    "attachment_avoidance":        "relational.attachment_avoidance",
    "conscientiousness":           "temporal.deadline_behavior",
    "emotional_stability":         "emotional.distress_tolerance",
    "extraversion":                "relational.social_energy",
    "openness":                    "cognitive.abstraction_level",
    "ambiguity_tolerance":         "meta_cognition.uncertainty_tolerance",
    "audio_tolerance":             "aesthetic.media_consumption",
    "checkin_tolerance":           "relational.help_seeking",
    "critique_tolerance":          "communication.conflict_style",
    "directness_preference":       "communication.directness",
    "emotional_intensity_tolerance":"emotional.distress_tolerance",
    "fictional_diegesis_tolerance":"meta_cognition.uncertainty_tolerance",
    "humor_tolerance":             "communication.humor_type",
    "image_tolerance":             "aesthetic.design_sensibility",
    "music_tolerance":             "aesthetic.media_consumption",
    "proactive_contact_tolerance": "relational.boundary_style",
}


@dataclass
class FacetState:
    facet_id: str
    category: str
    name: str
    description: str
    spectrum_low: str
    spectrum_high: str
    sensitivity: str
    intrusion_base: float
    value_position: float | None
    confidence: float          # 0.0–1.0
    observation_count: int
    last_observation_at: datetime | None
    asked_recently_hours: float  # hours since last check-in question


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def load_facet_states(conn: sqlite3.Connection, subject_baseline_path: Path | None = None) -> list[FacetState]:
    """Load all facets from db, merging bootstrap confidence if baseline provided."""
    now = datetime.now(timezone.utc)
    rows = conn.execute(
        """SELECT f.id, f.category, f.name, f.description, f.spectrum_low, f.spectrum_high,
                  f.sensitivity, f.intrusion_base,
                  t.value_position, t.confidence, t.observation_count, t.last_observation_at
           FROM facets f
           LEFT JOIN traits t ON t.facet_id = f.id"""
    ).fetchall()

    # Load bootstrap values for seeding initial confidence
    bootstrap: dict[str, float] = {}
    if subject_baseline_path and subject_baseline_path.exists():
        try:
            baseline = json.loads(subject_baseline_path.read_text(encoding="utf-8"))
            for section in ("psychological", "interaction"):
                for key, val in baseline.get(section, {}).items():
                    conf_str = val.get("confidence", "low_initial")
                    bootstrap[key] = CONFIDENCE_LEVEL_MAP.get(conf_str, 0.10)
        except Exception:
            pass

    # Hours since last check-in per facet
    checkin_rows = conn.execute(
        "SELECT facet_id, MAX(asked_at) FROM checkin_exchanges GROUP BY facet_id"
    ).fetchall()
    last_asked: dict[str, datetime] = {}
    for facet_id, asked_at in checkin_rows:
        dt = _parse_iso(asked_at)
        if dt:
            last_asked[facet_id] = dt

    states: list[FacetState] = []
    for row in rows:
        facet_id, cat, name, desc, sp_low, sp_high, sens, intrusion_base, \
            val_pos, conf_db, obs_count, last_obs_at = row

        # Use db confidence if observations exist, else bootstrap, else 0
        if (obs_count or 0) > 0 and conf_db is not None:
            confidence = float(conf_db)
        else:
            # Try to find a baseline key that maps to this facet
            bl_conf = 0.0
            for bl_key, db_id in _BASELINE_TO_DB.items():
                if db_id == facet_id and bl_key in bootstrap:
                    bl_conf = bootstrap[bl_key]
                    break
            confidence = bl_conf

        last_obs = _parse_iso(last_obs_at)
        asked_hours = 0.0
        if facet_id in last_asked:
            asked_hours = (now - last_asked[facet_id]).total_seconds() / 3600.0

        states.append(FacetState(
            facet_id=facet_id,
            category=cat,
            name=name,
            description=desc,
            spectrum_low=sp_low or "",
            spectrum_high=sp_high or "",
            sensitivity=sens or "media",
            intrusion_base=float(intrusion_base or 0.45),
            value_position=float(val_pos) if val_pos is not None else None,
            confidence=clamp(confidence),
            observation_count=int(obs_count or 0),
            last_observation_at=last_obs,
            asked_recently_hours=asked_hours,
        ))
    return states


def compute_unknownness(f: FacetState) -> float:
    now = datetime.now(timezone.utc)
    coverage_count = clamp(f.observation_count / 5.0)
    stale_days = 0.0
    if f.last_observation_at:
        stale_days = max(0.0, (now - f.last_observation_at).total_seconds() / 86400.0)
    elif f.confidence > 0:
        stale_days = 30.0  # bootstrap only, treat as somewhat stale
    else:
        stale_days = 60.0  # never observed
    stale_factor = clamp(stale_days / 60.0)
    unknown = 1.0 - (0.65 * f.confidence + 0.35 * coverage_count)
    unknown += 0.25 * stale_factor
    return clamp(unknown)


def compute_impact(f: FacetState) -> float:
    base = _CATEGORY_IMPACT.get(f.category, 0.60)
    return clamp(base)


def compute_timeliness(f: FacetState) -> float:
    base = 0.70
    if f.observation_count == 0:
        base += 0.15
    return clamp(base)


def compute_intrusion(f: FacetState) -> float:
    base = _SENSITIVITY_INTRUSION.get(f.sensitivity, 0.45)
    # Use db intrusion_base if meaningfully set
    base = max(base, f.intrusion_base)
    return clamp(base)


def compute_asked_recently(f: FacetState) -> float:
    h = f.asked_recently_hours
    if h == 0:
        return 0.0
    if h <= 72:
        return 1.0
    if h <= 168:
        return 0.6
    if h <= 336:
        return 0.3
    return 0.0


def score_facet(f: FacetState) -> dict[str, float]:
    u = compute_unknownness(f)
    i = compute_impact(f)
    t = compute_timeliness(f)
    intr = compute_intrusion(f)
    ar = compute_asked_recently(f)
    score = clamp(0.35 * u + 0.25 * i + 0.20 * t - 0.20 * intr - 0.15 * ar)
    return {
        "facet_id": f.facet_id,
        "score": round(score, 4),
        "unknownness": round(u, 4),
        "impact": round(i, 4),
        "timeliness": round(t, 4),
        "intrusion": round(intr, 4),
        "asked_recently": round(ar, 4),
        "observation_count": f.observation_count,
        "confidence": round(f.confidence, 4),
    }


def build_question_hint(f: FacetState) -> str:
    # Strip clinical scale references (ECR-R, DERS, SDT, ...) from description and spectrum.
    # Never expose facet_id or f.name: those may contain clinical terms.
    desc = SCALE_REF_RE.sub("", f.description).strip().rstrip(":").strip()
    sp_low = SCALE_REF_RE.sub("", f.spectrum_low).strip()
    sp_high = SCALE_REF_RE.sub("", f.spectrum_high).strip()
    if sp_low and sp_high:
        return f"{desc}. Spettro: {sp_low} ↔ {sp_high}."
    return desc


# Follow-up window: a replied exchange is a follow-up candidate while the
# reply is at most this old. Beyond it the thread has gone cold and a new
# TGS-selected topic reads more natural than reviving stale context.
FOLLOWUP_WINDOW_HOURS = 72

# Cap on the reply excerpt quoted back into the follow-up hint. Keeps the
# rendered topic block inside the 200-char budget of render_topic_hint.
_FOLLOWUP_EXCERPT_CHARS = 90


def select_followup(
    conn: sqlite3.Connection,
    now: datetime | None = None,
    window_hours: int = FOLLOWUP_WINDOW_HOURS,
) -> dict[str, Any] | None:
    """Return a follow-up candidate built from the latest answered exchange.

    Follow-up questions (not topic-switch questions) are the conversational
    move that deepens rapport (Huang et al. 2017, JPSP). A replied exchange is
    a candidate when:
      * its reply was captured within ``window_hours``;
      * no newer exchange was asked after the reply (i.e. the answer has not
        been followed up yet).

    Returns ``{"facet_id", "question_text", "reply_excerpt", "hint"}`` or
    ``None``. The hint is built mostly from the reply text so the Jaccard
    anti-repeat gate does not collide with the original question.
    """
    now = now or datetime.now(timezone.utc)
    try:
        row = conn.execute(
            """SELECT facet_id, question_text, reply_text, reply_captured_at
               FROM checkin_exchanges
               WHERE reply_text IS NOT NULL AND facet_id IS NOT NULL
               ORDER BY reply_captured_at DESC
               LIMIT 1"""
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    if not row:
        return None

    facet_id, question_text, reply_text, reply_at_iso = row
    reply_at = _parse_iso(reply_at_iso)
    if reply_at is None:
        return None
    if reply_at.tzinfo is None:
        reply_at = reply_at.replace(tzinfo=timezone.utc)
    if (now - reply_at).total_seconds() > window_hours * 3600:
        return None

    # Already followed up? Any exchange asked after the reply closes the thread.
    try:
        newer = conn.execute(
            "SELECT 1 FROM checkin_exchanges WHERE asked_at > ? LIMIT 1",
            (reply_at_iso,),
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    if newer:
        return None

    excerpt = " ".join((reply_text or "").split())[:_FOLLOWUP_EXCERPT_CHARS].strip()
    if not excerpt:
        return None

    hint = f"Approfondisci quello che ti ha risposto: «{excerpt}»."
    return {
        "facet_id": facet_id,
        "question_text": question_text or "",
        "reply_excerpt": excerpt,
        "hint": hint,
    }


def select_facet(
    conn: sqlite3.Connection,
    subject_baseline_path: Path | None = None,
    threshold: float = 0.30,
    top_k: int = 3,
    seed: int | None = None,
) -> dict[str, Any]:
    """Score all facets and return a weighted-random candidate from top-k above threshold.

    Args:
        seed: optional int seed for reproducible selection (e.g. hash of subject_id+date)
    """
    states = load_facet_states(conn, subject_baseline_path)
    if not states:
        return {"status": "no_facets", "reason": "empty_facet_registry"}

    ranking = sorted([score_facet(f) for f in states], key=lambda x: x["score"], reverse=True)
    top5 = ranking[:5]

    candidates = [r for r in ranking if r["score"] >= threshold]
    if not candidates:
        return {
            "status": "no_candidate",
            "reason": "no_facet_above_threshold",
            "threshold": threshold,
            "best_score": ranking[0]["score"],
            "ranking_top5": top5,
        }

    # Weighted random selection from top-k candidates above threshold
    pool = candidates[:top_k]
    weights = [r["score"] for r in pool]
    if not any(w > 0 for w in weights):
        selected = pool[0]
    else:
        rng = random.Random(seed)
        selected = rng.choices(pool, weights=weights, k=1)[0]

    f_state = next(s for s in states if s.facet_id == selected["facet_id"])

    return {
        "status": "ask_now",
        "selected_facet": selected["facet_id"],
        "question_hint": build_question_hint(f_state),
        "score": selected["score"],
        "threshold": threshold,
        "ranking_top5": top5,
        "now": datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    import argparse, os
    parser = argparse.ArgumentParser(description="Select next check-in facet via TGS")
    parser.add_argument("--subject-id", required=True)
    parser.add_argument("--db-path", default=None)
    parser.add_argument("--baseline-path", default=None)
    parser.add_argument("--threshold", type=float, default=0.30)
    args = parser.parse_args()

    relic_home = os.environ.get("RELIC_HOME", str(Path.home() / ".relic"))
    db_path = Path(args.db_path) if args.db_path else \
              Path(relic_home) / "subjects" / args.subject_id / "relic.db"
    baseline_path = Path(args.baseline_path) if args.baseline_path else \
                    Path(relic_home) / "subjects" / args.subject_id / "subject_baseline.json"

    conn = sqlite3.connect(str(db_path))
    result = select_facet(conn, baseline_path, threshold=args.threshold)
    conn.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
