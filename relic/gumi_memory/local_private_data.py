"""Local private-data redaction (PR19B / LOCAL_PRIVATE_DATA_TEST_CONTRACT).

The redactor is intentionally over-conservative: any free-text field that is
not in the allowlist is replaced with a hash placeholder before evaluation
artifacts leave the local machine.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

ALLOWED_KEYS = frozenset(
    {
        "candidate_id",
        "provider",
        "score",
        "redacted",
        "decision",
        "subject_id",  # treated opaque
    }
)


def _digest(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode()).hexdigest()[:12]


def redact_record(record: dict) -> dict:
    out: dict = {}
    for k, v in record.items():
        if k in ALLOWED_KEYS:
            if k == "subject_id" and isinstance(v, str):
                out[k] = _digest(v)
            else:
                out[k] = v
        else:
            out[k] = "[REDACTED]"
    return out


@dataclass(frozen=True)
class RedactionReport:
    total_fields: int
    redacted_fields: int

    @property
    def coverage(self) -> float:
        return self.redacted_fields / self.total_fields if self.total_fields else 1.0


def report_for(records: list[dict]) -> RedactionReport:
    total = sum(len(r) for r in records)
    redacted = sum(
        1 for r in records for k in r if k not in ALLOWED_KEYS
    )
    return RedactionReport(total_fields=total, redacted_fields=redacted)
