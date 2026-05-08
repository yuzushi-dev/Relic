"""PR19B — local private data must be redacted before reports leave the host."""
from __future__ import annotations

from relic.gumi_memory.local_private_data import (
    ALLOWED_KEYS,
    redact_record,
    report_for,
)


def test_unknown_keys_are_redacted() -> None:
    rec = {"raw_text": "secret", "candidate_id": "c1", "score": 0.5}
    out = redact_record(rec)
    assert out["raw_text"] == "[REDACTED]"
    assert out["candidate_id"] == "c1"
    assert out["score"] == 0.5


def test_subject_id_is_hashed() -> None:
    out = redact_record({"subject_id": "subj_001"})
    assert out["subject_id"].startswith("sha256:")


def test_report_coverage() -> None:
    r = report_for([{"a": 1, "b": 2}])
    assert r.coverage > 0
