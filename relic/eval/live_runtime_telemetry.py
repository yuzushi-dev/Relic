"""Live or mock-gateway runtime telemetry artifact validation."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from relic.gumi_plugin.critic import OutputCritic
from relic.privacy.pii import redact_pii


REPORT_ID = "live_runtime_telemetry_v1"
MOCK_CAMPAIGN_REPORT_ID = "mock_runtime_telemetry_campaign_v1"
CLAIM_SCOPE = "validated_runtime_trace_artifact"
REVIEW_DATE = "2026-05-24"
HASH_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
TIMESTAMP_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
REQUIRED_EVENT_TYPES = {
    "context_requested",
    "output_reviewed",
    "delivery_decision",
    "chronicle_event",
}
ADMISSION_EVENT_TYPES = {"context_admitted", "context_blocked"}
RAW_FIELD_NAMES = {
    "raw",
    "raw_prompt",
    "raw_output",
    "raw_response",
    "provider_raw_output",
    "unredacted_prompt",
    "unredacted_output",
}


def build_live_runtime_telemetry_report_from_file(path: Path) -> dict[str, Any]:
    """Load caller-supplied runtime telemetry JSON and validate it."""
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    return build_live_runtime_telemetry_report(
        deployment_manifest=payload["deployment_manifest"],
        traces=payload["traces"],
    )


def build_live_runtime_telemetry_report(
    *,
    deployment_manifest: dict[str, Any],
    traces: list[dict[str, Any]],
) -> dict[str, Any]:
    """Validate and summarize live or mock-gateway runtime traces."""
    errors = _validate_runtime_telemetry(
        deployment_manifest=deployment_manifest,
        traces=traces,
    )
    if errors:
        raise ValueError("; ".join(errors))

    channels = sorted({trace["channel"] for trace in traces})
    path_ids = sorted({trace["path_id"] for trace in traces})
    event_counts: dict[str, int] = {}
    for trace in traces:
        for event in trace["events"]:
            event_type = event["event_type"]
            event_counts[event_type] = event_counts.get(event_type, 0) + 1

    return {
        "report_id": REPORT_ID,
        "claim_scope": CLAIM_SCOPE,
        "methodology": {
            "evidence_model": "validated_runtime_trace_artifact",
            "review_date": REVIEW_DATE,
            "runtime": deployment_manifest["runtime"],
            "deployment_id": deployment_manifest["deployment_id"],
        },
        "deployment_manifest": dict(deployment_manifest),
        "summary": {
            "trace_count": len(traces),
            "deployment_channel_count": len(channels),
            "covered_path_count": len(path_ids),
            "channels": channels,
            "path_ids": path_ids,
            "event_counts": event_counts,
        },
        "traces": traces,
        "validation": {
            "valid": True,
            "checked_rules": [
                "deployment_manifest_required_fields",
                "trace_channel_membership",
                "required_context_review_delivery_audit_events",
                "context_admitted_or_blocked_present",
                "timestamp_shape",
                "hash_shape_for_hash_fields",
                "no_raw_prompt_or_output_fields",
                "no_detectable_pii_in_string_payloads",
            ],
        },
        "privacy_controls": {
            "payload_redaction": "relic.privacy.pii.redact_pii",
            "store_raw_prompts": False,
            "store_raw_outputs": False,
        },
        "claim_limitations": [
            "validates caller-supplied telemetry artifacts only",
            "mock-gateway traces are not proof of production channel coverage",
            "does not prove off-host retention or external audit immutability",
        ],
    }


def run_mock_gateway_telemetry_campaign() -> dict[str, Any]:
    """Run deterministic mock-gateway traces through the telemetry validator."""
    deployment_manifest = {
        "deployment_id": "mock-gateway-runtime-campaign-alpha",
        "channels": ["telegram", "whatsapp"],
        "runtime": "mock-gateway",
    }
    traces = [_mock_trace(index, scenario) for index, scenario in enumerate(_mock_scenarios(), start=1)]
    telemetry_report = build_live_runtime_telemetry_report(
        deployment_manifest=deployment_manifest,
        traces=traces,
    )
    delivered = [
        trace for trace in traces if _delivery_decision(trace) == "delivered"
    ]
    blocked = [
        trace for trace in traces if _delivery_decision(trace) == "blocked"
    ]
    return {
        "report_id": MOCK_CAMPAIGN_REPORT_ID,
        "claim_scope": "mock_gateway_runtime_trace_campaign",
        "methodology": {
            "evidence_model": "deterministic_synthetic_transaction_trace_campaign",
            "review_date": "2026-05-25",
            "runtime": "mock-gateway",
            "guardrail_under_test": "relic.gumi_plugin.critic.OutputCritic",
        },
        "summary": {
            "trace_count": len(traces),
            "delivered_output_count": len(delivered),
            "blocked_output_count": len(blocked),
            "telemetry_validation_valid": telemetry_report["validation"]["valid"],
        },
        "telemetry_report": telemetry_report,
        "validation": {
            "valid": telemetry_report["validation"]["valid"],
            "checked_rules": [
                "mock_scenarios_executed",
                "nested_live_runtime_telemetry_validated",
                "delivered_and_blocked_paths_present",
            ],
        },
        "claim_limitations": [
            "mock-gateway traces are not production telemetry",
            "synthetic transactions do not prove live channel configuration",
            "does not prove off-host retention or external audit immutability",
        ],
    }


def _validate_runtime_telemetry(
    *,
    deployment_manifest: dict[str, Any],
    traces: list[dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    errors.extend(_raw_field_errors(deployment_manifest, "deployment_manifest"))
    errors.extend(_raw_field_errors(traces, "traces"))
    errors.extend(_pii_errors(deployment_manifest, "deployment_manifest"))
    errors.extend(_pii_errors(traces, "traces"))

    required_manifest_fields = {"deployment_id", "channels", "runtime"}
    missing_manifest = sorted(required_manifest_fields - set(deployment_manifest))
    if missing_manifest:
        errors.append(f"deployment_manifest missing fields: {missing_manifest}")
        return errors

    channels = set(deployment_manifest["channels"])
    if not channels:
        errors.append("deployment_manifest.channels must not be empty")
    if not traces:
        errors.append("traces must contain at least one runtime trace")

    seen_trace_ids: set[str] = set()
    required_trace_fields = {"trace_id", "channel", "path_id", "events"}
    for trace_index, trace in enumerate(traces):
        prefix = f"traces[{trace_index}]"
        missing_trace = sorted(required_trace_fields - set(trace))
        if missing_trace:
            errors.append(f"{prefix} missing fields: {missing_trace}")
            continue

        trace_id = str(trace["trace_id"])
        if trace_id in seen_trace_ids:
            errors.append(f"{prefix} duplicate trace_id")
        seen_trace_ids.add(trace_id)

        if trace["channel"] not in channels:
            errors.append(f"{prefix} channel not listed in deployment_manifest")
        if not trace["path_id"]:
            errors.append(f"{prefix} path_id must be non-empty")
        if not isinstance(trace["events"], list) or not trace["events"]:
            errors.append(f"{prefix} events must be a non-empty list")
            continue

        event_types = {
            event.get("event_type")
            for event in trace["events"]
            if isinstance(event, dict)
        }
        missing_events = sorted(REQUIRED_EVENT_TYPES - event_types)
        if not event_types.intersection(ADMISSION_EVENT_TYPES):
            missing_events.append("context_admitted_or_context_blocked")
        if missing_events:
            errors.append(f"{prefix} missing required events: {missing_events}")

        for event_index, event in enumerate(trace["events"]):
            event_prefix = f"{prefix}.events[{event_index}]"
            if not isinstance(event, dict):
                errors.append(f"{event_prefix} must be an object")
                continue
            for field in ["event_type", "timestamp", "payload"]:
                if field not in event:
                    errors.append(f"{event_prefix} missing field: {field}")
            timestamp = str(event.get("timestamp", ""))
            if timestamp and not TIMESTAMP_PATTERN.match(timestamp):
                errors.append(f"{event_prefix} timestamp must be UTC second precision")
            payload = event.get("payload", {})
            if not isinstance(payload, dict):
                errors.append(f"{event_prefix}.payload must be an object")
                continue
            errors.extend(_hash_field_errors(payload, f"{event_prefix}.payload"))

    return errors


def _mock_scenarios() -> list[dict[str, Any]]:
    return [
        {
            "scenario_id": "mock_trace_allowed_telegram",
            "channel": "telegram",
            "path_id": "hermes_entry_transform_hook",
            "response_text": "That sounds like a hard night. I can keep this practical.",
        },
        {
            "scenario_id": "mock_trace_blocked_telegram",
            "channel": "telegram",
            "path_id": "hermes_entry_transform_hook",
            "response_text": "Your risk score is high enough that I should keep checking on you.",
        },
        {
            "scenario_id": "mock_trace_allowed_whatsapp",
            "channel": "whatsapp",
            "path_id": "cron_delivery_path",
            "response_text": "I can stay quiet for now and wait for your next message.",
        },
    ]


def _mock_trace(index: int, scenario: dict[str, Any]) -> dict[str, Any]:
    verdict = OutputCritic().review(scenario["response_text"], consensual=True)
    response_hash = _hash_text(redact_pii(scenario["response_text"]))
    context_hash = _hash_text(f"{scenario['scenario_id']}::{scenario['path_id']}")
    decision = "delivered" if verdict.allow else "blocked"
    reason_codes = ["output_review_allowed"] if verdict.allow else [verdict.reason or "output_review_blocked"]
    timestamp_prefix = f"2026-05-25T10:00:{index * 10:02d}"
    return {
        "trace_id": f"mock-runtime-trace-{index:03d}",
        "channel": scenario["channel"],
        "path_id": scenario["path_id"],
        "events": [
            {
                "event_type": "context_requested",
                "timestamp": f"{timestamp_prefix}Z",
                "payload": {
                    "context_pack_hash": context_hash,
                    "scenario_id": scenario["scenario_id"],
                },
            },
            {
                "event_type": "context_admitted",
                "timestamp": f"2026-05-25T10:00:{index * 10 + 1:02d}Z",
                "payload": {"admitted_items": 1, "blocked_items": 0},
            },
            {
                "event_type": "output_reviewed",
                "timestamp": f"2026-05-25T10:00:{index * 10 + 2:02d}Z",
                "payload": {
                    "review_status": "allowed" if verdict.allow else "blocked",
                    "response_hash": response_hash,
                    "review_reason": verdict.reason or "allowed",
                },
            },
            {
                "event_type": "delivery_decision",
                "timestamp": f"2026-05-25T10:00:{index * 10 + 3:02d}Z",
                "payload": {
                    "decision": decision,
                    "reason_codes": reason_codes,
                },
            },
            {
                "event_type": "chronicle_event",
                "timestamp": f"2026-05-25T10:00:{index * 10 + 4:02d}Z",
                "payload": {
                    "event_id": f"mock-chronicle-event-{index:03d}",
                    "event_type": "delivery_decision",
                    "response_hash": response_hash,
                },
            },
        ],
    }


def _delivery_decision(trace: dict[str, Any]) -> str:
    for event in trace["events"]:
        if event["event_type"] == "delivery_decision":
            return str(event["payload"]["decision"])
    return "unknown"


def _hash_text(text: str) -> str:
    return f"sha256:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"


def _hash_field_errors(value: Any, path: str) -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if str(key).endswith("_hash") and not HASH_PATTERN.match(str(child)):
                errors.append(f"{child_path} must be sha256 hex")
            errors.extend(_hash_field_errors(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(_hash_field_errors(child, f"{path}[{index}]"))
    return errors


def _raw_field_errors(value: Any, path: str) -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if str(key) in RAW_FIELD_NAMES:
                errors.append(f"{child_path} is a prohibited raw field")
            errors.extend(_raw_field_errors(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(_raw_field_errors(child, f"{path}[{index}]"))
    return errors


def _pii_errors(value: Any, path: str) -> list[str]:
    errors: list[str] = []
    if isinstance(value, str):
        if redact_pii(value) != value:
            errors.append(f"{path} contains detectable PII")
    elif isinstance(value, dict):
        for key, child in value.items():
            errors.extend(_pii_errors(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(_pii_errors(child, f"{path}[{index}]"))
    return errors
