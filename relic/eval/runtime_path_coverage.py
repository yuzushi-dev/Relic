"""Runtime path coverage inventory for scientific defensibility review.

This report is an assurance-style inventory: it maps runtime claims to code and
test evidence, and it names gaps explicitly. It is not live deployment telemetry.
"""

from __future__ import annotations

from collections import Counter
from typing import Any


STATUS_VALUES = {
    "covered",
    "partial",
    "compatibility_surface",
    "not_live_default",
    "unresolved",
}


def _runtime_invariants() -> list[dict[str, Any]]:
    return [
        {
            "invariant_id": "subject_scope",
            "claim": "Runtime state is scoped to a subject/Gumi/Hermes profile boundary.",
            "required_evidence": [
                "session key or runtime envelope includes subject/profile scope",
                "tests reject missing or cross-subject scope",
            ],
            "failure_if_missing": "A context, delivery, or memory path could cross subject boundaries.",
        },
        {
            "invariant_id": "context_admission",
            "claim": "Context injected into Gumi passes an admission or fail-closed gate.",
            "required_evidence": [
                "context pack construction has blocked-item handling",
                "hook failures return no injected context",
            ],
            "failure_if_missing": "Blocked or researcher-only material could reach the model prompt.",
        },
        {
            "invariant_id": "output_review",
            "claim": "Subject-facing output is reviewed or sanitized before delivery.",
            "required_evidence": [
                "output critic or sanitizer is called before stdout/API delivery",
                "tests cover clinical terms, backend disclosure, dependency, or operator text",
            ],
            "failure_if_missing": "Unsafe or operator-facing text could be delivered to the subject.",
        },
        {
            "invariant_id": "delivery_gate",
            "claim": "Outbound delivery is gated by consent, allowlist, quiet-hours, or delivery target state.",
            "required_evidence": [
                "delivery decision objects include reason codes",
                "tests cover blocked allowlist, quiet hours, local/dry-run defaults, or consent withdrawal",
            ],
            "failure_if_missing": "Proactive or resumed messages could bypass participant delivery controls.",
        },
        {
            "invariant_id": "pause_forget_resume",
            "claim": "Pause, forget, and resume controls affect continuity recall and proactive delivery.",
            "required_evidence": [
                "Shared Continuity exposes pause/forget/resume operations",
                "cron and recall tests exercise pause or forget state",
            ],
            "failure_if_missing": "A withdrawn or paused continuity scope could continue influencing Gumi.",
        },
        {
            "invariant_id": "durable_continuity",
            "claim": "Shared Continuity marker state can survive service restarts with marker-level lifecycle audit events.",
            "required_evidence": [
                "SQLite-backed repository reloads confirmed markers after restart",
                "authoritative corrections and forget events persist with subject scope",
            ],
            "failure_if_missing": "A longitudinal memory claim would rest on in-process state that disappears across restarts.",
        },
        {
            "invariant_id": "resume_reconciliation",
            "claim": "Checkpoint/session resume re-checks state before releasing pending output.",
            "required_evidence": [
                "resume reconciliation checks delivery, pause, TTL, safety, and sanitizer state",
                "tests cover unknown delivery state and pending-output hold",
            ],
            "failure_if_missing": "A pending output could be delivered under stale safety or consent state.",
        },
        {
            "invariant_id": "chronicle_audit",
            "claim": "Governance decisions emit redacted, inspectable audit evidence where the path supports it.",
            "required_evidence": [
                "Chronicle or JSONL decision event emission exists",
                "tests or code references identify emitted event types and redaction boundaries",
            ],
            "failure_if_missing": "Researchers cannot reconstruct why a runtime decision occurred.",
        },
        {
            "invariant_id": "safety_signal_isolation",
            "claim": "Researcher-facing safety signals are not injected as Gumi memory or labels.",
            "required_evidence": [
                "safety extraction/audit is separate from continuity recall",
                "tests reject safety-signal memory injection or clinicalization",
            ],
            "failure_if_missing": "Safety governance could become hidden clinical memory.",
        },
    ]


def _entry(
    *,
    path_id: str,
    entrypoint: str,
    status: str,
    claim: str,
    controls: list[str],
    code_paths: list[str],
    test_paths: list[str],
    arguments: list[str],
    gaps: list[str],
) -> dict[str, Any]:
    if status not in STATUS_VALUES:
        raise ValueError(f"unknown runtime path coverage status: {status}")
    return {
        "path_id": path_id,
        "entrypoint": entrypoint,
        "status": status,
        "claim": claim,
        "controls": controls,
        "evidence": {
            "code_paths": code_paths,
            "test_paths": test_paths,
            "arguments": arguments,
        },
        "gaps": gaps,
    }


def _path_inventory() -> list[dict[str, Any]]:
    return [
        _entry(
            path_id="hermes_plugin_pcp_injection",
            entrypoint="RelicHermesPlugin.inject_ephemeral_context / HookManager.pre_llm_call",
            status="covered",
            claim="In-process Hermes plugin context injection is subject-scoped, ephemeral, and fail-closed.",
            controls=["subject_scope", "context_admission", "pause_forget_resume"],
            code_paths=[
                "relic/hermes_plugin/plugin.py",
                "relic/hermes_plugin/hooks.py",
                "relic/hermes_plugin/context_injection.py",
            ],
            test_paths=[
                "tests/hermes_plugin/test_context_pack_ephemeral_not_system_prompt.py",
                "tests/hermes_compat/test_plugin_failure_no_injection.py",
                "tests/hermes_compat/test_no_soul_memory_user_mutation.py",
            ],
            arguments=[
                "Plugin state, pause state, disabled config, and fail-safe state all return no injected context.",
                "Context pack results are per-turn data, not persistent SOUL/MEMORY/USER mutation.",
            ],
            gaps=[
                "This proves the installed plugin path, not every external Hermes hook installation.",
            ],
        ),
        _entry(
            path_id="standalone_shared_continuity_adapter_hook",
            entrypoint="hermes-plugin/tools/relic_shared_continuity/hooks_adapter.py",
            status="partial",
            claim="The adapter-enhanced standalone hook emits runtime envelopes, context admission events, and output-review events.",
            controls=[
                "subject_scope",
                "context_admission",
                "output_review",
                "chronicle_audit",
                "safety_signal_isolation",
            ],
            code_paths=[
                "hermes-plugin/tools/relic_shared_continuity/hooks_adapter.py",
                "relic/hermes_adapter/hooks.py",
                "relic/hermes_adapter/envelope.py",
            ],
            test_paths=[
                "tests/hermes_compat/test_runtime_envelope.py",
                "tests/hermes_compat/test_chronicle_event_types.py",
                "tests/shared-continuity/test_hermes_hooks.py",
            ],
            arguments=[
                "The adapter creates a runtime envelope, emits context requested/admitted/blocked/rendered events, and reviews output.",
                "Safety scans are best-effort and audit-facing rather than continuity memory.",
            ],
            gaps=[
                "Coverage is partial until Hermes deployment configuration proves this adapter hook is the active hook.",
                "Hook bootstrap keeps some behavior best-effort so live telemetry is still required for deployment claims.",
            ],
        ),
        _entry(
            path_id="standalone_shared_continuity_legacy_hook",
            entrypoint="hermes-plugin/tools/relic_shared_continuity/hooks.py",
            status="compatibility_surface",
            claim="The legacy standalone hook remains a compatibility surface with fail-closed context injection and output filtering.",
            controls=["context_admission", "output_review", "safety_signal_isolation"],
            code_paths=[
                "hermes-plugin/tools/relic_shared_continuity/hooks.py",
                "hermes-plugin/tools/relic_shared_continuity/tools.py",
            ],
            test_paths=[
                "tests/shared-continuity/test_hermes_hooks.py",
                "tests/hermes_compat/test_plugin_context_injection.py",
                "tests/hermes_compat/test_plugin_failure_no_injection.py",
            ],
            arguments=[
                "The hook returns no context on failures and applies a fallback output filter.",
                "It does not provide the same adapter-level envelope and Chronicle coverage as hooks_adapter.py.",
            ],
            gaps=[
                "Compatibility path can bypass adapter-normalized evidence if deployed instead of hooks_adapter.py.",
                "Migration or deployment inventory is needed before claiming all live Hermes hooks use the adapter.",
            ],
        ),
        _entry(
            path_id="hermes_entry_transform_hook",
            entrypoint="relic.hermes_plugin.hermes_entry.register / transform_llm_output",
            status="covered",
            claim="The packaged Hermes entry transform hook applies OutputCritic semantic output review before subject-facing output is returned.",
            controls=["output_review"],
            code_paths=[
                "relic/hermes_plugin/hermes_entry/__init__.py",
                "relic/gumi_plugin/critic.py",
                "relic/gumi_plugin/output_sanitizer.py",
            ],
            test_paths=[
                "tests/hermes_plugin/test_hermes_entry.py",
                "tests/gumi_plugin/test_output_critic_nonclinical_boundary.py",
            ],
            arguments=[
                "The registered transform hook reviews response_text with OutputCritic before the line sanitizer.",
                "Semantic clinical overreach is transformed on the packaged Hermes entry path, not only in direct Gumi dispatch.",
                "Operator-facing line filtering remains in the sanitizer after critic review.",
            ],
            gaps=[
                "This is still contract-level evidence for the registered entry hook, not live gateway telemetry proving the hook is installed in a running deployment.",
            ],
        ),
        _entry(
            path_id="no_agent_cron_decision",
            entrypoint="relic.gumi_plugin.cron_wiring.make_decision",
            status="partial",
            claim="No-agent cron decisions apply pause, allowlist, quiet-hours, cadence, and candidate/delivery decision gates.",
            controls=[
                "delivery_gate",
                "pause_forget_resume",
                "chronicle_audit",
            ],
            code_paths=[
                "relic/gumi_plugin/cron_wiring.py",
                "relic/hermes_runtime.py",
                "relic/hermes_adapter/cron_bridge.py",
            ],
            test_paths=[
                "tests/gumi_plugin/test_cron_pause_controller_gate.py",
                "tests/hermes_compat/test_cron_bridge.py",
                "tests/hermes/test_no_agent_cron_wiring.py",
            ],
            arguments=[
                "The decision path emits structured RuntimeDecision values and JSONL/Chronicle-style decision evidence.",
                "Pause, quiet-hours, allowlist, and continuity scope checks can return NO_REPLY or BLOCKED before delivery.",
            ],
            gaps=[
                "Some helper failures are fail-open, so live monitoring must verify when they occur.",
                "The force path intentionally bypasses several gates for manual testing and must remain excluded from study deployment claims.",
            ],
        ),
        _entry(
            path_id="checkin_dispatch_delivery",
            entrypoint="relic.gumi_plugin.checkin_media_dispatcher.dispatch",
            status="covered",
            claim="Post-LLM dispatch sanitizes subject-facing output and defaults non-local delivery to explicit Telegram/API configuration.",
            controls=["output_review", "delivery_gate", "chronicle_audit"],
            code_paths=[
                "relic/gumi_plugin/checkin_media_dispatcher.py",
                "relic/gumi_plugin/output_sanitizer.py",
                "relic/gumi_plugin/critic.py",
            ],
            test_paths=[
                "tests/gumi_plugin/test_dispatch_pipeline.py",
                "tests/gumi_plugin/test_output_sanitizer.py",
                "tests/gumi_plugin/test_stdout_discipline.py",
            ],
            arguments=[
                "The dispatcher runs the output critic before text, voice, image, or music delivery branches.",
                "Subject-facing stdout is sanitized; operator warnings and media traces go to stderr.",
                "Delivered events are written only after Telegram delivery succeeds.",
            ],
            gaps=[
                "The dispatcher is downstream of gate output; it does not independently reconstruct every consent decision.",
            ],
        ),
        _entry(
            path_id="resume_reconciliation",
            entrypoint="relic.hermes_plugin.resume_hooks.check_pending_output_reconciliation",
            status="covered",
            claim="Resume hooks hold pending output for review when delivery, safety, pause, TTL, sanitizer, or state knowledge checks fail.",
            controls=[
                "subject_scope",
                "delivery_gate",
                "pause_forget_resume",
                "resume_reconciliation",
            ],
            code_paths=[
                "relic/hermes_plugin/resume_hooks.py",
                "relic/hermes_runtime.py",
            ],
            test_paths=[
                "tests/hermes/test_resume_reconciliation.py",
                "tests/cli/test_wire06_resume_reconciliation.py",
            ],
            arguments=[
                "Unknown delivery state is review-required, and pending output is held rather than auto-delivered.",
                "Session key mismatch, paused continuity scope, expired markers, and sanitizer blocks are checked.",
            ],
            gaps=[
                "This verifies the Relic reconciliation hook contract; live Hermes resume wiring still needs deployment evidence.",
            ],
        ),
        _entry(
            path_id="shared_continuity_sqlite_repository",
            entrypoint="relic.shared_continuity.repository.SQLiteContinuityRepository",
            status="covered",
            claim="Shared Continuity has a SQLite repository that persists confirmed markers, authoritative corrections, scope state, and marker-level audit events across service restarts.",
            controls=[
                "subject_scope",
                "pause_forget_resume",
                "durable_continuity",
                "chronicle_audit",
                "safety_signal_isolation",
            ],
            code_paths=[
                "relic/shared_continuity/repository.py",
                "relic/shared_continuity/service.py",
                "relic/db/migrations/0013_shared_continuity.sql",
            ],
            test_paths=[
                "tests/shared-continuity/test_durable_sqlite_repository.py",
                "tests/shared-continuity/test_continuity_service.py",
                "tests/shared-continuity/test_recent_markers_excludes_safety_signals.py",
            ],
            arguments=[
                "Confirmed markers are written to SQLite and loaded into a fresh ContinuityService instance.",
                "Corrections persist both the superseded marker state and the new authoritative marker.",
                "Marker-created, correction-created, forget, pause, and resume events are queryable by subject and marker.",
                "Backup/restore drill creates a SQLite backup snapshot, verifies SHA-256 and PRAGMA integrity_check, restores to a new database, and rechecks marker/event row counts.",
            ],
            gaps=[
                "This is repository-level durability evidence, not live Hermes deployment telemetry.",
                "It does not by itself prove scheduled production backup operations, off-host storage, or multi-week participant retention under load.",
            ],
        ),
        _entry(
            path_id="hermes_handoff_gate",
            entrypoint="relic.hermes_adapter.handoff_gate.evaluate_handoff",
            status="partial",
            claim="Hermes handoff requests have a policy gate and Chronicle event path for authorization, blocking, or review.",
            controls=["subject_scope", "delivery_gate", "chronicle_audit"],
            code_paths=[
                "relic/hermes_adapter/handoff_gate.py",
                "relic/hermes_adapter/chronicle_helper.py",
            ],
            test_paths=[
                "tests/hermes_compat/test_phase567.py",
                "tests/hermes_compat/test_runtime_envelope.py",
            ],
            arguments=[
                "The handoff gate returns structured decisions and emits decision-category events.",
                "The request includes source and target profile IDs for traceable policy decisions.",
            ],
            gaps=[
                "Current risk detectors for cross-subject and untrusted-model transitions are placeholders.",
                "More negative tests are needed before handoff can support a strong safety claim.",
            ],
        ),
        _entry(
            path_id="gumi_hook_registry",
            entrypoint="relic.gumi_plugin.hooks.dispatch",
            status="covered",
            claim="The in-process Gumi hook registry dispatches lifecycle hooks fail-closed when handlers raise.",
            controls=["context_admission", "output_review"],
            code_paths=[
                "relic/gumi_plugin/hooks.py",
                "relic/hermes_plugin/plugin.py",
            ],
            test_paths=[
                "tests/gumi_plugin/test_plugin_fail_closed_no_injection.py",
                "tests/hermes_plugin/test_pre_send_hook.py",
                "tests/hermes_plugin/test_inject_context_hook_registered.py",
            ],
            arguments=[
                "Handler exceptions return None instead of injecting error objects into context.",
                "Plugin load registers pre-LLM, post-LLM, and pre-send controls for in-process paths.",
            ],
            gaps=[
                "The registry is local process state and is not itself proof of external Hermes gateway configuration.",
            ],
        ),
        _entry(
            path_id="live_gateway_delivery_adapters",
            entrypoint="Telegram live gateway plus WhatsApp/Email/SMS delivery adapters",
            status="unresolved",
            claim="Non-local live delivery adapters cannot yet be claimed as fully covered across every channel.",
            controls=["delivery_gate", "output_review", "chronicle_audit"],
            code_paths=[
                "relic/gumi_plugin/checkin_media_dispatcher.py",
                "docs/research/paper-codebase-map.md",
                "public-docs/guides/running-evaluations.md",
            ],
            test_paths=[
                "tests/gumi_plugin/test_dispatch_pipeline.py",
                "tests/gumi_plugin/test_checkin_media_dispatcher.py",
                "tests/hermes/test_platform_allowlist_contract.py",
            ],
            arguments=[
                "Telegram dispatch has tests and local/dry-run defaults; other public-alpha channels are documented as not implemented.",
                "A deployment claim needs per-channel adapter tests and live or mock-gateway traces.",
            ],
            gaps=[
                "WhatsApp, Email, and SMS are not implemented delivery adapters in the public alpha.",
                "Live Hermes end-to-end gateway traces are outside this static inventory.",
            ],
        ),
    ]


def _summary(entries: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(entry["status"] for entry in entries)
    return {
        "total_paths": len(entries),
        "covered_paths": counts["covered"],
        "partial_paths": counts["partial"],
        "compatibility_surface_paths": counts["compatibility_surface"],
        "not_live_default_paths": counts["not_live_default"],
        "unresolved_paths": counts["unresolved"],
        "global_runtime_claim_supported": False,
    }


def build_runtime_path_coverage_report() -> dict[str, Any]:
    """Build a machine-readable runtime coverage inventory."""
    entries = _path_inventory()
    return {
        "report_id": "runtime_path_coverage_v1",
        "claim_scope": "static_contract_inventory",
        "methodology": {
            "evidence_model": "claims_arguments_evidence",
            "conformance_frame": "architecture_conformance_inventory",
            "review_date": "2026-05-24",
        },
        "runtime_invariants": _runtime_invariants(),
        "path_inventory": entries,
        "summary": _summary(entries),
        "limitations": [
            "This is not live Hermes deployment telemetry.",
            "This is not participant evidence, clinical validation, or proof of longitudinal deployment safety.",
            "Coverage status is based on code and contract-test evidence available in this repository.",
            "Compatibility surfaces and unresolved channels must be excluded from strong global runtime claims.",
        ],
        "next_required_evidence": [
            "Hermes deployment manifest proving which hooks are active per profile.",
            "Mock-gateway or live-gateway traces for resume, cron, retry, and delivery paths.",
            "Per-channel delivery adapter tests before claiming non-Telegram channel coverage.",
            "Chronicle query coverage showing event reconstruction for sampled runtime decisions.",
            "Scheduled/off-host backup operations and multi-week retention drills for the Shared Continuity SQLite backend.",
        ],
    }
