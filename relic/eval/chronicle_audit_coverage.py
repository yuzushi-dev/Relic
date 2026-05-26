"""Chronicle audit reconstruction coverage inventory.

The report maps auditability claims to query surfaces, code paths, and tests.
It does not claim live telemetry, cryptographic immutability, or a completed
researcher task study.
"""

from __future__ import annotations

from collections import Counter
from typing import Any


STATUS_VALUES = {"supported", "partial", "unsupported"}


def _question(
    *,
    question_id: str,
    question: str,
    status: str,
    query_surface: str,
    required_records: list[str],
    code_paths: list[str],
    test_paths: list[str],
    gaps: list[str] | None = None,
) -> dict[str, Any]:
    if status not in STATUS_VALUES:
        raise ValueError(f"unknown Chronicle coverage status: {status}")
    return {
        "question_id": question_id,
        "question": question,
        "status": status,
        "query_surface": query_surface,
        "required_records": required_records,
        "evidence": {
            "code_paths": code_paths,
            "test_paths": test_paths,
        },
        "gaps": gaps or [],
    }


def _reconstruction_questions() -> list[dict[str, Any]]:
    code_common = [
        "relic/chronicle/schema.py",
        "relic/chronicle/emitter.py",
        "relic/chronicle/reader.py",
    ]
    acceptance = ["tests/chronicle/test_acceptance.py"]
    return [
        _question(
            question_id="Q01_session_timeline",
            question="What happened in this session?",
            status="supported",
            query_surface="query_events(session_id=...) / chronicle timeline --session",
            required_records=["chronicle_events.session_id", "chronicle_events.timestamp"],
            code_paths=code_common + ["relic/chronicle/cli/main.py"],
            test_paths=acceptance + ["tests/chronicle/test_reader.py"],
        ),
        _question(
            question_id="Q02_agent_actor",
            question="Which agent or module acted?",
            status="supported",
            query_surface="query_events(trace_id=...) filtered by agent_id/source_module",
            required_records=["chronicle_events.agent_id", "chronicle_events.source_module"],
            code_paths=code_common,
            test_paths=acceptance,
        ),
        _question(
            question_id="Q03_model_called",
            question="Which model was called?",
            status="supported",
            query_surface="query_events(event_type='model_called')",
            required_records=["chronicle_events.payload.model_id", "chronicle_events.payload_hash"],
            code_paths=code_common,
            test_paths=acceptance,
        ),
        _question(
            question_id="Q04_prompt_hash",
            question="Which prompt digest governed the model call?",
            status="supported",
            query_surface="query_events(event_type='model_called')",
            required_records=["chronicle_events.payload.prompt_hash"],
            code_paths=code_common,
            test_paths=acceptance,
        ),
        _question(
            question_id="Q05_response_hash",
            question="Which response digest was returned?",
            status="supported",
            query_surface="query_events(event_type='model_returned')",
            required_records=["chronicle_events.payload.response_hash"],
            code_paths=code_common,
            test_paths=acceptance,
        ),
        _question(
            question_id="Q06_tool_called",
            question="Which tool was called and with what argument digest?",
            status="supported",
            query_surface="query_events(event_type='tool_called')",
            required_records=["chronicle_events.payload.tool_name", "chronicle_events.payload.args_hash"],
            code_paths=code_common,
            test_paths=acceptance,
        ),
        _question(
            question_id="Q07_tool_result",
            question="What did the tool return?",
            status="supported",
            query_surface="query_events(event_type='tool_returned')",
            required_records=["chronicle_events.payload.outcome", "chronicle_events.payload.result_hash"],
            code_paths=code_common,
            test_paths=acceptance,
        ),
        _question(
            question_id="Q08_memory_reads",
            question="What memory read occurred?",
            status="supported",
            query_surface="query_events(event_type='memory_read')",
            required_records=["chronicle_events.event_type", "chronicle_events.payload"],
            code_paths=code_common,
            test_paths=acceptance,
        ),
        _question(
            question_id="Q09_memory_writes",
            question="What memory write occurred?",
            status="supported",
            query_surface="query_events(event_type='memory_write')",
            required_records=["chronicle_events.event_type", "chronicle_events.payload.marker_hash"],
            code_paths=code_common,
            test_paths=acceptance,
        ),
        _question(
            question_id="Q10_profile_read",
            question="Which profile was read?",
            status="supported",
            query_surface="query_events(event_type='profile_read')",
            required_records=["chronicle_events.profile_id"],
            code_paths=code_common,
            test_paths=acceptance,
        ),
        _question(
            question_id="Q11_profile_modified",
            question="Which profile field was modified?",
            status="supported",
            query_surface="query_events(event_type='profile_write_applied')",
            required_records=["chronicle_events.profile_id", "chronicle_events.payload.field_path"],
            code_paths=code_common,
            test_paths=acceptance,
        ),
        _question(
            question_id="Q12_snapshot_diff",
            question="Can a profile/state diff be reconstructed from snapshots?",
            status="supported",
            query_surface="query_snapshots(subject_id=..., snapshot_type=...)",
            required_records=[
                "chronicle_state_snapshots.snapshot_id",
                "chronicle_state_snapshots.previous_snapshot_id",
                "chronicle_state_snapshots.content_hash",
            ],
            code_paths=["relic/chronicle/snapshots.py", "relic/chronicle/reader.py"],
            test_paths=acceptance + ["tests/chronicle/test_snapshots.py"],
        ),
        _question(
            question_id="Q13_decision_records",
            question="Which decision was made?",
            status="supported",
            query_surface="query_decisions(trace_id=...) / chronicle decision --trace",
            required_records=["chronicle_decisions.decision_kind", "chronicle_decisions.selected_action"],
            code_paths=code_common + ["relic/chronicle/cli/main.py"],
            test_paths=acceptance + ["tests/chronicle/test_reader.py"],
        ),
        _question(
            question_id="Q14_decision_evidence",
            question="Which evidence references supported the decision?",
            status="supported",
            query_surface="query_decisions(trace_id=...)",
            required_records=["chronicle_decisions.evidence_refs", "chronicle_decisions.rationale_summary"],
            code_paths=code_common,
            test_paths=acceptance,
        ),
        _question(
            question_id="Q15_error_records",
            question="What error occurred?",
            status="supported",
            query_surface="query_events(event_type='error_raised')",
            required_records=["chronicle_events.error_code", "chronicle_events.severity"],
            code_paths=code_common,
            test_paths=acceptance,
        ),
        _question(
            question_id="Q16_retry_records",
            question="Was there a retry and what parent event caused it?",
            status="supported",
            query_surface="query_events(event_type='retry_started')",
            required_records=["chronicle_events.parent_event_id", "chronicle_events.retry_count"],
            code_paths=code_common,
            test_paths=acceptance,
        ),
        _question(
            question_id="Q17_artifacts_generated",
            question="Which artifact was generated or registered?",
            status="supported",
            query_surface="query_events(event_type='artifact_registered')",
            required_records=["chronicle_events.payload.artifact_id"],
            code_paths=code_common,
            test_paths=acceptance,
        ),
        _question(
            question_id="Q18_provenance_subgraph",
            question="Which upstream records generated an artifact?",
            status="supported",
            query_surface="get_ancestors(artifact_id) / chronicle provenance --direction ancestors",
            required_records=[
                "chronicle_provenance_edges.artifact_id",
                "chronicle_provenance_edges.from_node_id",
                "chronicle_provenance_edges.relation",
            ],
            code_paths=["relic/chronicle/provenance.py", "relic/chronicle/emitter.py"],
            test_paths=acceptance + ["tests/chronicle/test_provenance.py"],
        ),
        _question(
            question_id="Q19_sensitive_filter",
            question="Can sensitive events be filtered?",
            status="supported",
            query_surface="query_events(sensitivity=...)",
            required_records=["chronicle_events.sensitivity"],
            code_paths=code_common,
            test_paths=acceptance + ["tests/chronicle/test_redaction.py"],
        ),
        _question(
            question_id="Q20_consent_basis",
            question="Which consent or legitimate-interest basis applied?",
            status="supported",
            query_surface="query_events(trace_id=...) with consent_basis field",
            required_records=["chronicle_events.consent_basis"],
            code_paths=["relic/chronicle/schema.py", "relic/chronicle/consent_gate.py"],
            test_paths=acceptance + ["tests/chronicle/test_consent_gate.py"],
        ),
        _question(
            question_id="Q21_subject_export_count",
            question="Can subject-scoped records be exported or counted?",
            status="supported",
            query_surface="query_events(subject_id=...) / chronicle export --subject",
            required_records=["chronicle_events.subject_id", "chronicle_decisions.subject_id"],
            code_paths=["relic/chronicle/reader.py", "relic/chronicle/cli/main.py"],
            test_paths=acceptance + ["tests/chronicle/test_access_audit.py"],
        ),
        _question(
            question_id="Q22_deletion_dry_run",
            question="Can deletion/reaper impact be estimated before destructive action?",
            status="supported",
            query_surface="reaper_run(dry_run=True, subject_id=...) / chronicle delete --dry-run",
            required_records=[
                "chronicle_events.subject_id",
                "chronicle_decisions.subject_id",
                "retention_policy",
            ],
            code_paths=["relic/chronicle/retention.py", "relic/chronicle/cli/main.py"],
            test_paths=acceptance + ["tests/chronicle/test_retention.py"],
        ),
        _question(
            question_id="Q23_retention_policy_counts",
            question="Can events be grouped by retention policy?",
            status="supported",
            query_surface="query_events(trace_id=...) and stats(subject_id=...)",
            required_records=["chronicle_events.retention_policy"],
            code_paths=["relic/chronicle/reader.py", "relic/chronicle/retention.py"],
            test_paths=acceptance + ["tests/chronicle/test_retention.py"],
        ),
    ]


def _capability(
    *,
    capability_id: str,
    status: str,
    claim: str,
    evidence: list[str],
    tests: list[str],
    gaps: list[str] | None = None,
) -> dict[str, Any]:
    if status not in STATUS_VALUES:
        raise ValueError(f"unknown Chronicle capability status: {status}")
    return {
        "capability_id": capability_id,
        "status": status,
        "claim": claim,
        "evidence": {
            "code_paths": evidence,
            "test_paths": tests,
        },
        "gaps": gaps or [],
    }


def _audit_capabilities() -> list[dict[str, Any]]:
    return [
        _capability(
            capability_id="event_schema",
            status="supported",
            claim="Events have typed IDs, trace/session/subject scope, source modules, timestamps, payload hashes, retention, visibility, and sensitivity fields.",
            evidence=["relic/chronicle/schema.py"],
            tests=["tests/chronicle/test_schema.py", "tests/chronicle/test_acceptance.py"],
        ),
        _capability(
            capability_id="decision_schema",
            status="supported",
            claim="Decisions record selected actions, rejected alternatives, evidence references, rationale summaries, and validation status.",
            evidence=["relic/chronicle/schema.py", "relic/chronicle/emitter.py"],
            tests=["tests/chronicle/test_schema.py", "tests/chronicle/test_acceptance.py"],
        ),
        _capability(
            capability_id="trace_join",
            status="supported",
            claim="Trace IDs join events, decisions, and optional snapshots for reconstruction.",
            evidence=["relic/chronicle/reader.py"],
            tests=["tests/chronicle/test_reader.py", "tests/chronicle/test_acceptance.py"],
        ),
        _capability(
            capability_id="subject_query",
            status="supported",
            claim="Subject-scoped query and export paths exist for event-ledger inspection.",
            evidence=["relic/chronicle/reader.py", "relic/chronicle/cli/main.py"],
            tests=["tests/chronicle/test_reader.py", "tests/chronicle/test_acceptance.py"],
        ),
        _capability(
            capability_id="provenance_graph",
            status="supported",
            claim="Artifact provenance edges use PROV-O relation names and can be queried for ancestors/descendants.",
            evidence=["relic/chronicle/provenance.py", "relic/chronicle/enums.py"],
            tests=["tests/chronicle/test_provenance.py", "tests/chronicle/test_acceptance.py"],
        ),
        _capability(
            capability_id="access_audit",
            status="supported",
            claim="Researcher-mode reads, exports, and deletes can be logged as access audit records.",
            evidence=["relic/chronicle/access_audit.py", "relic/chronicle/cli/main.py"],
            tests=["tests/chronicle/test_access_audit.py"],
        ),
        _capability(
            capability_id="retention_reaper",
            status="supported",
            claim="Retention policies drive dry-run and delete behavior, with legal-hold style policies excluded from auto deletion.",
            evidence=["relic/chronicle/retention.py", "relic/chronicle/enums.py"],
            tests=["tests/chronicle/test_retention.py", "tests/chronicle/test_acceptance.py"],
        ),
        _capability(
            capability_id="export_bundle",
            status="supported",
            claim="Chronicle export writes subject-scoped events, decisions, snapshots, and a manifest.",
            evidence=["relic/chronicle/cli/main.py"],
            tests=["tests/chronicle/test_acceptance.py", "tests/chronicle/test_access_audit.py"],
        ),
        _capability(
            capability_id="journal_verify_repair",
            status="partial",
            claim="JSONL journal rows can be compared against SQLite and replayed with --repair.",
            evidence=["relic/chronicle/cli/main.py", "relic/chronicle/emitter.py"],
            tests=["tests/chronicle/test_emitter.py"],
            gaps=[
                "The static report does not execute a corrupt-journal recovery drill.",
                "The repair path is local SQLite/JSONL reconciliation, not independent third-party attestation.",
            ],
        ),
        _capability(
            capability_id="payload_hashing",
            status="partial",
            claim="Payloads are hashed with stable JSON serialization for deduplication and integrity checks.",
            evidence=["relic/chronicle/emitter.py", "relic/chronicle/schema.py"],
            tests=["tests/chronicle/test_schema.py", "tests/chronicle/test_emitter.py"],
            gaps=[
                "Payload hashes are not a ledger-level hash chain.",
                "There is no cryptographic signature, Merkle root, or external timestamp authority in the public artifact.",
            ],
        ),
        _capability(
            capability_id="redaction_guard",
            status="supported",
            claim="Payload redaction prevents common secrets from being written into Chronicle records.",
            evidence=["relic/chronicle/redaction.py", "relic/chronicle/emitter.py"],
            tests=["tests/chronicle/test_redaction.py"],
        ),
        _capability(
            capability_id="consent_basis",
            status="supported",
            claim="Events validate consent or legitimate-interest bases for sensitive governance records.",
            evidence=["relic/chronicle/schema.py", "relic/chronicle/consent_gate.py"],
            tests=["tests/chronicle/test_consent_gate.py", "tests/chronicle/test_acceptance.py"],
        ),
    ]


def _minimum_reconstruction_fields() -> dict[str, list[str]]:
    return {
        "chronicle_event": [
            "event_id",
            "event_type",
            "event_category",
            "trace_id",
            "run_id",
            "session_id",
            "parent_event_id",
            "subject_id",
            "agent_id",
            "profile_id",
            "hermes_profile_id",
            "actor_type",
            "actor_id",
            "source_module",
            "timestamp",
            "input_refs",
            "output_refs",
            "payload_hash",
            "payload_redacted",
            "sensitivity",
            "visibility",
            "consent_basis",
            "retention_policy",
            "severity",
            "schema_version",
        ],
        "chronicle_decision": [
            "decision_id",
            "trace_id",
            "session_id",
            "subject_id",
            "actor_type",
            "actor_id",
            "decision_kind",
            "selected_action",
            "rejected_alternatives",
            "observable_inputs",
            "observable_outputs",
            "evidence_refs",
            "rationale_summary",
            "sensitivity",
            "validation_status",
            "timestamp",
            "schema_version",
        ],
        "chronicle_provenance_edge": [
            "edge_id",
            "artifact_id",
            "from_node_type",
            "from_node_id",
            "relation",
            "contribution_role",
            "trace_id",
            "timestamp",
        ],
    }


def _summary(
    questions: list[dict[str, Any]],
    capabilities: list[dict[str, Any]],
) -> dict[str, Any]:
    question_counts = Counter(question["status"] for question in questions)
    capability_counts = Counter(capability["status"] for capability in capabilities)
    return {
        "reconstruction_questions": len(questions),
        "supported_questions": question_counts["supported"],
        "partial_questions": question_counts["partial"],
        "unsupported_questions": question_counts["unsupported"],
        "capabilities": len(capabilities),
        "supported_capabilities": capability_counts["supported"],
        "partial_capabilities": capability_counts["partial"],
        "unsupported_capabilities": capability_counts["unsupported"],
        "global_audit_claim_supported": False,
    }


def build_chronicle_audit_coverage_report() -> dict[str, Any]:
    """Build a machine-readable Chronicle audit reconstruction inventory."""
    questions = _reconstruction_questions()
    capabilities = _audit_capabilities()
    return {
        "report_id": "chronicle_audit_coverage_v1",
        "claim_scope": "static_query_reconstruction_inventory",
        "methodology": {
            "evidence_model": "audit_trail_reconstruction_matrix",
            "provenance_model": "W3C_PROV_O_aligned",
            "review_date": "2026-05-24",
        },
        "reconstruction_questions": questions,
        "audit_capabilities": capabilities,
        "minimum_reconstruction_fields": _minimum_reconstruction_fields(),
        "summary": _summary(questions, capabilities),
        "limitations": [
            "This is not live runtime telemetry.",
            "This is not a cryptographically signed or Merkle-chained ledger.",
            "This is not a completed researcher usability or audit-reconstruction task study.",
            "This report maps repository code and tests; it does not prove every deployed runtime emitted the expected events.",
            "Chronicle records decisions and structured evidence, not raw hidden chain-of-thought or unrestricted private content.",
        ],
        "next_required_evidence": [
            "Run seeded reconstruction drills through the Chronicle CLI and record timings and error rates.",
            "Capture live or mock Hermes runtime traces for cron, resume, delivery, and handoff paths.",
            "Add a journal-corruption and repair drill with before/after SQLite visibility evidence.",
            "Add cryptographic hash-chain or external timestamping only if the paper needs tamper-evidence claims.",
            "Run a researcher Workbench/CLI task study for audit interpretation and reconstruction accuracy.",
        ],
    }
