"""Proactive queue consumer (Plan §Task 9).

Pulls one candidate from ``<RELIC_HOME>/subjects/<id>/proactive_queue.jsonl``
and turns it into a ``make_decision``-shaped tuple. Expired or low-salience
candidates are skipped; consumed entries are rewritten out so the queue
shrinks deterministically. Does not deliver — returns the tuple so the
downstream dispatch path is the same as the legacy proactivity lane.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from relic.hermes_runtime import RuntimeDecision, RuntimeDecisionReason

logger = logging.getLogger(__name__)


def _queue_path(subject_id: str, relic_home: Optional[Path] = None) -> Path:
    if relic_home is None:
        relic_home = Path(os.environ.get("RELIC_HOME") or Path.home() / ".relic")
    return Path(relic_home) / "subjects" / subject_id / "proactive_queue.jsonl"


def load_candidates(path: Path) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    out: list[dict] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def save_candidates(path: Path, candidates: list[dict]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        for row in candidates:
            fh.write(json.dumps(row) + "\n")
    tmp.replace(path)


def _to_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def consume_one(
    subject_id: str,
    hermes_home: Path,
    relic_home: Optional[Path] = None,
    *,
    now: Optional[datetime] = None,
    min_priority: float = 0.5,
) -> tuple[RuntimeDecision, list[RuntimeDecisionReason], Optional[dict]]:
    """Pop the highest-priority unexpired candidate and convert it to a decision tuple.

    Behaviour:
      - empty queue or no eligible candidate → (NO_REPLY, [no_due_work], None);
      - candidate accepted → (DELIVER, [no_due_work], {"message": ..., ...});
      - low priority candidates are dropped from the queue silently.
    """
    now = now or datetime.now(timezone.utc)
    path = _queue_path(subject_id, relic_home)
    candidates = load_candidates(path)
    if not candidates:
        return RuntimeDecision.NO_REPLY, [RuntimeDecisionReason.no_due_work], None

    remaining: list[dict] = []
    chosen: Optional[dict] = None
    for row in candidates:
        if row.get("consumed_at"):
            remaining.append(row)
            continue
        expires_at = _to_dt(row.get("expires_at"))
        if expires_at is not None and expires_at <= now:
            # expired — drop silently.
            continue
        priority = float(row.get("priority", 0.0) or 0.0)
        if priority < min_priority:
            # below floor — drop.
            continue
        if chosen is None or float(row.get("priority", 0.0)) > float(chosen.get("priority", 0.0)):
            if chosen is not None:
                remaining.append(chosen)
            chosen = row
        else:
            remaining.append(row)

    if chosen is None:
        save_candidates(path, remaining)
        return RuntimeDecision.NO_REPLY, [RuntimeDecisionReason.no_due_work], None

    chosen["consumed_at"] = now.isoformat()
    remaining.append(chosen)
    save_candidates(path, remaining)

    base_message = "DELIVER\ntipo: text\nora: -\nproactive: true"
    candidate_data = {
        "message": base_message,
        "decision_type": "proactivity",
        "proactive_signal_ref": chosen.get("signal_ref"),
        "suggested_posture": chosen.get("suggested_posture"),
        "priority": chosen.get("priority"),
        "candidate_id": chosen.get("id"),
    }
    return RuntimeDecision.DELIVER, [RuntimeDecisionReason.no_due_work], candidate_data


def _proactive_queue_enabled() -> bool:
    return os.environ.get("RELIC_PROACTIVE_QUEUE_ENABLED", "").strip().lower() in ("1", "true", "yes")
