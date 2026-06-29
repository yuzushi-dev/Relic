"""Passive observation extraction from subject Telegram messages.

Reads `role='user'` messages from the Hermes `state.db` (since a per-subject
watermark) so that the subject's free-form conversation can advance facet
coverage, not just explicit check-in replies. This module currently provides
the candidate-loading step; attribution + observation writing land in later
tasks.

Mirrors the query/filters of
`relic.checkin.context_builder.build_recent_subject_messages_section`:
table `messages`, `role='user'`, drop NULL content and `[IMPORTANT:` cron
prompts. Reply scaffolds are stripped and non-substantive messages dropped via
`relic.checkin.reply_capture` (anti-bleed; see `project_diegetic_bleed_followup`).
"""
from __future__ import annotations

import json
import logging
import os
import random
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from relic.checkin import attribution_jury
from relic.checkin.facet_updater import extract_observation
from relic.checkin.passive_state import get_watermark, set_watermark
from relic.checkin.reply_capture import _is_substantive, strip_reply_quote_prefix

logger = logging.getLogger(__name__)

# Passive evidence must be clear: drop any extracted signal weaker than this.
PASSIVE_STRENGTH_FLOOR = 0.5

# Vision/media captions are injected as role='user' content (e.g.
# "[The user sent an image~ Here's what I can see: ...]"). They are a model's
# description, NOT the subject's words — attributing them would contaminate the
# subject's profile, so they are dropped like cron prompts.
_MEDIA_CAPTION_PREFIX = "[The user sent"


def load_new_messages(
    state_db_path: str | Path,
    since_ts: float,
    limit: int = 20,
) -> list[dict]:
    """Load cleaned, substantive subject messages newer than `since_ts`.

    Opens the Hermes `state.db` read-only and pulls `role='user'` rows with
    non-NULL content that are not cron prompts (`[IMPORTANT:`), newer than
    `since_ts`, ascending by timestamp and bounded by `limit` (caps jury cost
    per run). Each row has its Telegram reply scaffold stripped and is kept
    only if substantive.

    Returns `[{"ts": float, "text": str}]`. Fail-open: on a missing file or any
    sqlite error, logs a WARNING and returns `[]`.
    """
    db_path = Path(state_db_path)
    if not db_path.exists():
        logger.warning(
            "[checkin] passive_extractor: state.db missing db_path=%s", db_path
        )
        return []

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5.0)
        try:
            rows = conn.execute(
                """SELECT content, timestamp
                   FROM messages
                   WHERE role='user'
                     AND timestamp > ?
                     AND content IS NOT NULL
                     AND content NOT LIKE '[IMPORTANT:%'
                   ORDER BY timestamp ASC
                   LIMIT ?""",
                (since_ts, limit),
            ).fetchall()
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.warning(
            "[checkin] passive_extractor: %s: %s db_path=%s",
            type(e).__name__, e, db_path,
        )
        return []

    out: list[dict] = []
    for content, ts in rows:
        text = strip_reply_quote_prefix(content)
        if text.lstrip().startswith(_MEDIA_CAPTION_PREFIX):
            continue  # vision/media caption, not the subject's words
        if not _is_substantive(text):
            continue
        out.append({"ts": float(ts), "text": text})
    return out


def attribute_message(
    text: str,
    facets: dict,
    *,
    judge_fn=None,
    rng: random.Random | None = None,
) -> str | None:
    """Attribute a single cleaned message to a facet (or None) via the jury.

    Fresh attribution (no recorded facet): the cross-family panel + lexical
    voter must reach majority + >=2 families on a real facet for it to win.
    The jury was built to *validate a recorded facet*, so we pass
    `recorded="NONE"` to `aggregate` — a real facet only wins when the panel
    converges on it (otherwise the message stays unattributed).

    `judge_fn` defaults to `attribution_jury.llm_choose` (network); tests inject
    a fake panel. `rng` defaults to a fresh `random.Random()`.
    """
    judge_fn = judge_fn or attribution_jury.llm_choose
    rng = rng or random.Random()

    cands = attribution_jury.lexical_candidates(text, facets)
    if not cands:
        return None

    votes: list[str] = []
    by_judge: dict[str, list[str]] = {}
    for model, template in attribution_jury.JUDGES:
        for _ in range(attribution_jury.SAMPLES):
            shuffled = cands[:]
            rng.shuffle(shuffled)
            vote = judge_fn(
                model, reply=text, question="", candidates=shuffled,
                template=template,
            )
            if vote is not None:
                votes.append(vote)
                by_judge.setdefault(model, []).append(vote)
    votes.append(attribution_jury.lexical_best(text, cands, facets))

    res = attribution_jury.aggregate(recorded="NONE", votes=votes, by_judge=by_judge)
    target = res["target"]
    if target and target != "NONE":
        return target
    return None


def extract_and_write(
    conn: sqlite3.Connection,
    facet_id: str,
    facets: dict,
    text: str,
    ts: float,
    *,
    llm_client=None,
    dry_run: bool = False,
    strength_floor: float = PASSIVE_STRENGTH_FLOOR,
) -> dict:
    """Extract a behavioral signal for a confirmed (message, facet) pair and
    persist a `source_type='passive_chat'` observation in relic.db.

    Reuses `facet_updater.extract_observation`: the message is passed as
    `reply_text` and a synthesized `question_text` grounds the facet. There is
    no real check-in exchange, so `exchange_id=0` is passed purely for the
    result's logging field — `extract_observation` never mutates
    `checkin_exchanges`.

    Drops anything that errors, is not informative, or whose `signal_strength`
    is below `strength_floor` (passive evidence must be clear). The insert
    mirrors `facet_updater.process_pending_exchanges` (`INSERT OR IGNORE`,
    dedup on `(facet_id, source_ref)`); `source_ref = f"msg:{int(ts)}"`. Writes
    NOTHING to the `traits` table — `synthesize_traits` owns that.

    Returns `{"written": False, "reason": ...}` when nothing is persisted, or
    `{"written": True, "facet_id", "signal_position", "signal_strength"}`.
    """
    facet = facets[facet_id]
    description = facet.get("description") or ""
    question_text = f"(osservazione passiva) {description}"

    extraction = extract_observation(
        exchange_id=0,
        facet_id=facet_id,
        facet_name=facet.get("name") or facet_id,
        description=description,
        spectrum_low=facet.get("spectrum_low") or "low",
        spectrum_high=facet.get("spectrum_high") or "high",
        question_text=question_text,
        reply_text=text,
        llm_client=llm_client,
    )

    if extraction.error:
        return {"written": False, "reason": extraction.error}
    if not extraction.informative:
        return {"written": False, "reason": "not_informative"}
    if extraction.signal_strength < strength_floor:
        return {"written": False, "reason": "weak_signal"}

    if not dry_run:
        now_iso = datetime.now(timezone.utc).isoformat()
        try:
            conn.execute(
                """INSERT OR IGNORE INTO observations
                   (facet_id, source_type, source_ref, content, extracted_signal,
                    signal_strength, signal_position, created_at)
                   VALUES (?, 'passive_chat', ?, ?, ?, ?, ?, ?)""",
                (
                    facet_id,
                    f"msg:{int(ts)}",
                    extraction.observation_summary,
                    json.dumps({"question": question_text[:100]}),
                    extraction.signal_strength,
                    extraction.signal_position,
                    now_iso,
                ),
            )
            conn.commit()
        except sqlite3.Error:
            conn.rollback()
            return {"written": False, "reason": "db_error"}

    return {
        "written": True,
        "facet_id": facet_id,
        "signal_position": extraction.signal_position,
        "signal_strength": extraction.signal_strength,
    }


def run_passive_extraction(
    conn: sqlite3.Connection,
    subject_id: str,
    state_db_path: str | Path,
    facets: dict,
    *,
    relic_home: str | Path | None = None,
    delivery_policy_path: str | Path | None = None,
    judge_fn=None,
    llm_client=None,
    rng: random.Random | None = None,
    dry_run: bool = False,
) -> dict:
    """Run passive extraction for one subject end-to-end (consent-gated).

    Ties together loading (Task 3), jury attribution (Task 4) and signal
    extraction + observation write (Task 5), bounded by the per-subject
    watermark (idempotency) and gated by the `consent_for_passive_extraction`
    opt-in in `delivery_policy.json` (default OFF).

    Consent loading mirrors `reply_capture.capture_reply_if_pending`: the policy
    lives at `relic_home/subjects/<id>/delivery_policy.json`. Fail-closed —
    a missing/unreadable policy or a falsy/missing flag means NO consent, and
    messages are never read.

    Returns `{"skipped": "no_consent"}` when consent is absent, otherwise
    `{"processed", "attributed", "written", "watermark"}`.
    """
    if delivery_policy_path is not None:
        dp_path = Path(delivery_policy_path)
    else:
        base = Path(relic_home or os.environ.get("RELIC_HOME", Path.home() / ".relic"))
        dp_path = base / "subjects" / subject_id / "delivery_policy.json"

    # Fail-closed consent gate (mirror reply_capture.capture_reply_if_pending).
    if not dp_path.exists():
        return {"skipped": "no_consent"}
    try:
        dp = json.loads(dp_path.read_text(encoding="utf-8"))
        if not dp.get("consent_for_passive_extraction", False):
            return {"skipped": "no_consent"}
    except Exception:
        logger.debug(
            "run_passive_extraction: delivery_policy load failed", exc_info=True
        )
        return {"skipped": "no_consent"}

    since = get_watermark(conn, subject_id)
    msgs = load_new_messages(state_db_path, since)
    if not msgs:
        return {"processed": 0, "attributed": 0, "written": 0, "watermark": since}

    n_attr = 0
    n_written = 0
    for msg in msgs:
        facet = attribute_message(
            msg["text"], facets, judge_fn=judge_fn, rng=rng
        )
        if facet:
            n_attr += 1
            res = extract_and_write(
                conn, facet, facets, msg["text"], msg["ts"],
                llm_client=llm_client, dry_run=dry_run,
            )
            if res.get("written"):
                n_written += 1

    watermark = since
    if not dry_run:
        watermark = max(m["ts"] for m in msgs)
        set_watermark(conn, subject_id, watermark)

    return {
        "processed": len(msgs),
        "attributed": n_attr,
        "written": n_written,
        "watermark": watermark,
    }


def run_for_hermes_home(
    hermes_home: str | Path,
    *,
    relic_home: str | Path | None = None,
    subject_id: str | None = None,
    dry_run: bool = False,
) -> dict:
    """Run passive extraction for the ONE subject tied to this ``$HERMES_HOME``.

    PRIVACY SAFETY: the ``memory_sync`` cron runs under a single profile's
    ``$HERMES_HOME``, whose ``state.db`` holds only that subject's Telegram
    messages. This entrypoint resolves exactly that subject and reads exactly
    ``<hermes_home>/state.db``. It MUST NEVER iterate all subjects — writing
    subject A's messages as subject B's observations would be a privacy
    incident — so it does NOT go through the global ``_process_pending_facets``
    loop.

    Subject resolution order: explicit ``subject_id`` arg, then
    ``$RELIC_SUBJECT_ID``, then the ``hermes_home`` directory name with a
    leading ``gumi-``/``hermes-`` prefix stripped.

    HARD GUARD: returns ``{"skipped": "unresolved_subject", ...}`` and does
    NOTHING (no reads, no writes) unless the subject is unambiguously resolved
    AND both its own ``<hermes_home>/state.db`` and
    ``<relic_home>/subjects/<id>/relic.db`` exist. This refusal is what
    prevents cross-subject contamination.

    Fail-open: any exception returns ``{"error": ..., "subject_id": ...}``
    (never raises) so the cron's stdout contract is preserved.
    """
    hermes_home = Path(hermes_home)
    relic_home = Path(
        relic_home or os.environ.get("RELIC_HOME", Path.home() / ".relic")
    )

    # The owner of hermes_home is authoritative: we read hermes_home/state.db,
    # so the subject MUST be whoever owns that home. Derive it from the dir name.
    owner = hermes_home.name
    for prefix in ("gumi-", "hermes-"):
        if owner.startswith(prefix):
            owner = owner[len(prefix):]
            break
    owner = owner or None

    # An explicit arg or $RELIC_SUBJECT_ID may scope the run, but if it disagrees
    # with the home owner it is unsafe (state.db belongs to a different subject
    # than the relic.db we'd write) — refuse rather than risk cross-subject bleed.
    explicit = subject_id or os.environ.get("RELIC_SUBJECT_ID") or None
    if explicit and owner and explicit != owner:
        return {"skipped": "subject_mismatch", "hermes_owner": owner, "requested": explicit}
    subject_id = explicit or owner

    try:
        state_db_path = hermes_home / "state.db"
        relic_db_path = relic_home / "subjects" / str(subject_id) / "relic.db"

        # HARD GUARD (cross-subject safety): never touch any data unless the
        # subject is resolved and BOTH of its own DBs exist.
        if (
            not subject_id
            or not state_db_path.exists()
            or not relic_db_path.exists()
        ):
            return {"skipped": "unresolved_subject", "subject_id": subject_id}

        conn = sqlite3.connect(str(relic_db_path))
        try:
            facets = {
                r[0]: {
                    "name": r[1],
                    "description": r[2],
                    "spectrum_low": r[3],
                    "spectrum_high": r[4],
                }
                for r in conn.execute(
                    "SELECT id,name,description,spectrum_low,spectrum_high FROM facets"
                )
            }
            result = run_passive_extraction(
                conn,
                subject_id,
                state_db_path,
                facets,
                relic_home=relic_home,
                dry_run=dry_run,
            )
        finally:
            conn.close()

        result["subject_id"] = subject_id
        return result
    except Exception as exc:  # fail-open: never break the cron
        logger.warning(
            "[checkin] run_for_hermes_home failed subject_id=%s: %s",
            subject_id, exc,
        )
        return {"error": str(exc), "subject_id": subject_id}


def main(argv: list[str] | None = None) -> int:
    """CLI: run passive extraction for one subject's ``$HERMES_HOME``."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Run passive observation extraction for one subject's $HERMES_HOME",
    )
    parser.add_argument(
        "--hermes-home",
        default=os.environ.get("HERMES_HOME", str(Path.home() / ".hermes")),
    )
    parser.add_argument("--subject-id", default=None)
    parser.add_argument("--relic-home", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    result = run_for_hermes_home(
        args.hermes_home,
        relic_home=args.relic_home,
        subject_id=args.subject_id,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
