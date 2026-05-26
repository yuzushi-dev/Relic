"""Synthetic multi-subject Shared Continuity isolation/load drill."""

from __future__ import annotations

import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from relic.shared_continuity.repository import SQLiteContinuityRepository
from relic.shared_continuity.service import ContinuityService


REPORT_ID = "multi_subject_isolation_load_v1"
CLAIM_SCOPE = "synthetic_multi_subject_researcher_load"
REVIEW_DATE = "2026-05-25"


def build_multi_subject_isolation_load_report(
    *,
    db_path: str | Path | None = None,
    subject_count: int = 12,
    researcher_count: int = 3,
    markers_per_subject: int = 4,
    worker_count: int = 4,
) -> dict[str, Any]:
    """Exercise subject-scoped Shared Continuity reads/writes under synthetic load."""
    if subject_count < 2:
        raise ValueError("subject_count must be at least 2")
    if researcher_count < 1:
        raise ValueError("researcher_count must be at least 1")
    if markers_per_subject < 1:
        raise ValueError("markers_per_subject must be at least 1")

    if db_path is None:
        with tempfile.TemporaryDirectory(prefix="relic-multi-subject-load-") as tmpdir:
            return _run_load_drill(
                db_path=Path(tmpdir) / "continuity-load.db",
                subject_count=subject_count,
                researcher_count=researcher_count,
                markers_per_subject=markers_per_subject,
                worker_count=worker_count,
            )
    return _run_load_drill(
        db_path=Path(db_path),
        subject_count=subject_count,
        researcher_count=researcher_count,
        markers_per_subject=markers_per_subject,
        worker_count=worker_count,
    )


def _run_load_drill(
    *,
    db_path: Path,
    subject_count: int,
    researcher_count: int,
    markers_per_subject: int,
    worker_count: int,
) -> dict[str, Any]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    subjects = [_subject(index) for index in range(1, subject_count + 1)]
    worker_total = min(max(1, worker_count), subject_count)
    with ThreadPoolExecutor(max_workers=worker_total) as executor:
        subject_results = list(
            executor.map(
                lambda subject: _write_subject_markers(
                    db_path=db_path,
                    subject=subject,
                    markers_per_subject=markers_per_subject,
                ),
                subjects,
            )
        )

    repository = SQLiteContinuityRepository(db_path)
    service = ContinuityService(repository=repository)
    researcher_assignments = _researcher_assignments(subjects, researcher_count)
    read_results = [
        _read_subject_scope(
            repository=repository,
            service=service,
            researcher_id=researcher_id,
            subject=subject,
            expected_marker_count=markers_per_subject,
            expected_tokens=expected_tokens,
        )
        for researcher_id, assigned_subjects in researcher_assignments.items()
        for subject in assigned_subjects
        for expected_tokens in [_tokens_for_subject(subject, markers_per_subject)]
    ]

    subject_summaries = [
        {
            "subject_id": result["subject_id"],
            "created_marker_count": result["created_marker_count"],
        }
        for result in subject_results
    ]
    stored_marker_count = sum(result["recent_marker_count"] for result in read_results)
    cross_subject_leak_count = sum(result["cross_subject_leak_count"] for result in read_results)
    event_subject_mismatch_count = sum(
        result["event_subject_mismatch_count"] for result in read_results
    )
    unconfirmed_candidate_recall_count = sum(
        result["unconfirmed_candidate_recall_count"] for result in read_results
    )
    incomplete_subject_count = sum(
        1
        for result in read_results
        if result["recent_marker_count"] != markers_per_subject
    )
    all_invariants_passed = (
        stored_marker_count == subject_count * markers_per_subject
        and cross_subject_leak_count == 0
        and event_subject_mismatch_count == 0
        and unconfirmed_candidate_recall_count == 0
        and incomplete_subject_count == 0
    )

    return {
        "report_id": REPORT_ID,
        "claim_scope": CLAIM_SCOPE,
        "methodology": {
            "evidence_model": "synthetic_multi_subject_shared_continuity_load_drill",
            "review_date": REVIEW_DATE,
            "repository": "SQLiteContinuityRepository",
            "service": "ContinuityService",
            "worker_count": worker_total,
        },
        "summary": {
            "subject_count": subject_count,
            "researcher_count": researcher_count,
            "marker_create_attempt_count": subject_count * markers_per_subject,
            "stored_marker_count": stored_marker_count,
            "candidate_marker_count": subject_count,
            "cross_subject_leak_count": cross_subject_leak_count,
            "event_subject_mismatch_count": event_subject_mismatch_count,
            "unconfirmed_candidate_recall_count": unconfirmed_candidate_recall_count,
            "incomplete_subject_count": incomplete_subject_count,
            "all_invariants_passed": all_invariants_passed,
        },
        "researcher_assignments": researcher_assignments,
        "subject_summaries": subject_summaries,
        "read_scope_results": read_results,
        "validation": {
            "valid": all_invariants_passed,
            "checked_rules": [
                "concurrent_subject_marker_writes",
                "subject_scoped_recent_marker_reads",
                "subject_scoped_audit_event_reads",
                "unconfirmed_candidates_excluded_from_runtime_recall",
                "cross_subject_subject_word_tokens_absent_from_scoped_reads",
            ],
        },
        "claim_limitations": [
            "synthetic local SQLite load drill only",
            "does not prove production deployment throughput or latency",
            "does not prove researcher authentication or authorization controls",
            "does not replace longitudinal participant evidence or live runtime telemetry",
        ],
    }


def _write_subject_markers(
    *,
    db_path: Path,
    subject: dict[str, str],
    markers_per_subject: int,
) -> dict[str, Any]:
    service = ContinuityService(repository=SQLiteContinuityRepository(db_path))
    created = []
    for marker_index in range(1, markers_per_subject + 1):
        token = _token(subject["subject_id"], marker_index)
        created.append(
            service.remember(
                subject_id=subject["subject_id"],
                gumi_instance_id=subject["gumi_instance_id"],
                hermes_profile_id=subject["hermes_profile_id"],
                subject_words=[f"remember {token}"],
                source_type="subject_confirmed",
                gumi_agreed_words=[token],
                max_recall_count=markers_per_subject + 2,
                ttl_seconds=3600,
                subject_confirmation=True,
            )
        )
    service.propose_candidate(
        subject_id=subject["subject_id"],
        gumi_instance_id=subject["gumi_instance_id"],
        hermes_profile_id=subject["hermes_profile_id"],
        subject_words=[f"unconfirmed {_token(subject['subject_id'], 999)}"],
        source_type="hindsight",
    )
    return {
        "subject_id": subject["subject_id"],
        "created_marker_count": len(created),
    }


def _read_subject_scope(
    *,
    repository: SQLiteContinuityRepository,
    service: ContinuityService,
    researcher_id: str,
    subject: dict[str, str],
    expected_marker_count: int,
    expected_tokens: set[str],
) -> dict[str, Any]:
    markers = service.recent_markers(
        subject_id=subject["subject_id"],
        gumi_instance_id=subject["gumi_instance_id"],
        hermes_profile_id=subject["hermes_profile_id"],
        limit=expected_marker_count + 5,
    )
    events = repository.list_events(subject_id=subject["subject_id"])
    recalled_text = " ".join(
        word
        for marker in markers
        for field in ("subject_words", "gumi_agreed_words")
        for word in marker.get(field, [])
    )
    subject_scope_mismatches = [
        marker.get("marker_id")
        for marker in markers
        if marker.get("subject_id") != subject["subject_id"]
    ]
    event_subject_mismatches = [
        event["event_id"]
        for event in events
        if event["subject_id"] != subject["subject_id"]
    ]
    other_tokens = _all_other_tokens(subject["subject_id"], expected_marker_count)
    leaked_tokens = sorted(token for token in other_tokens if token in recalled_text)
    missing_expected_tokens = sorted(
        token for token in expected_tokens if token not in recalled_text
    )
    candidate_token = _token(subject["subject_id"], 999)
    return {
        "researcher_id": researcher_id,
        "subject_id": subject["subject_id"],
        "recent_marker_count": len(markers),
        "audit_event_count": len(events),
        "subject_scope_mismatch_count": len(subject_scope_mismatches),
        "event_subject_mismatch_count": len(event_subject_mismatches),
        "cross_subject_leak_count": len(leaked_tokens),
        "unconfirmed_candidate_recall_count": 1 if candidate_token in recalled_text else 0,
        "missing_expected_token_count": len(missing_expected_tokens),
    }


def _researcher_assignments(
    subjects: list[dict[str, str]],
    researcher_count: int,
) -> dict[str, list[dict[str, str]]]:
    assignments = {
        f"researcher_{index:03d}": []
        for index in range(1, researcher_count + 1)
    }
    researcher_ids = list(assignments)
    for index, subject in enumerate(subjects):
        assignments[researcher_ids[index % researcher_count]].append(subject)
    return assignments


def _subject(index: int) -> dict[str, str]:
    subject_id = f"subj_load_{index:03d}"
    return {
        "subject_id": subject_id,
        "gumi_instance_id": f"gumi_load_{index:03d}",
        "hermes_profile_id": f"hermes_load_{index:03d}",
    }


def _tokens_for_subject(subject: dict[str, str], markers_per_subject: int) -> set[str]:
    return {
        _token(subject["subject_id"], marker_index)
        for marker_index in range(1, markers_per_subject + 1)
    }


def _all_other_tokens(subject_id: str, markers_per_subject: int) -> set[str]:
    return {
        _token(f"subj_load_{subject_index:03d}", marker_index)
        for subject_index in range(1, 100)
        for marker_index in range(1, markers_per_subject + 1)
        if f"subj_load_{subject_index:03d}" != subject_id
    }


def _token(subject_id: str, marker_index: int) -> str:
    return f"{subject_id}_token_{marker_index:03d}"
