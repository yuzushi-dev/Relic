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

import logging
import sqlite3
from pathlib import Path

from relic.checkin.reply_capture import _is_substantive, strip_reply_quote_prefix

logger = logging.getLogger(__name__)


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
        if not _is_substantive(text):
            continue
        out.append({"ts": float(ts), "text": text})
    return out
