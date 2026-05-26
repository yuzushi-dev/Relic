"""Live runtime telemetry artifact contracts."""

from __future__ import annotations

import json

from scripts import eval_run
from relic.eval.live_runtime_telemetry import (
    build_live_runtime_telemetry_report,
    run_mock_gateway_telemetry_campaign,
)


def test_live_runtime_telemetry_report_validates_required_trace_events():
    report = build_live_runtime_telemetry_report(
        deployment_manifest={
            "deployment_id": "mock-gateway-2026-05",
            "channels": ["telegram", "whatsapp"],
            "runtime": "mock-gateway",
        },
        traces=[
            _trace("trace-1", "telegram", "hermes_entry_transform_hook"),
            _trace("trace-2", "whatsapp", "cron_delivery_path"),
        ],
    )

    assert report["report_id"] == "live_runtime_telemetry_v1"
    assert report["claim_scope"] == "validated_runtime_trace_artifact"
    assert report["validation"]["valid"] is True
    assert report["summary"]["trace_count"] == 2
    assert report["summary"]["deployment_channel_count"] == 2
    assert report["summary"]["covered_path_count"] == 2
    assert "raw_output" not in json.dumps(report["traces"])


def test_live_runtime_telemetry_report_rejects_raw_or_incomplete_traces():
    try:
        build_live_runtime_telemetry_report(
            deployment_manifest={
                "deployment_id": "mock-gateway-2026-05",
                "channels": ["telegram"],
                "runtime": "mock-gateway",
            },
            traces=[
                {
                    "trace_id": "trace-1",
                    "channel": "telegram",
                    "path_id": "hermes_entry_transform_hook",
                    "events": [
                        {
                            "event_type": "context_requested",
                            "timestamp": "2026-05-24T10:00:00Z",
                            "payload": {"raw_output": "unredacted provider text"},
                        }
                    ],
                }
            ],
        )
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("expected invalid telemetry artifact to be rejected")

    assert "raw_output" in message
    assert "missing required events" in message


def test_eval_run_live_runtime_telemetry_imports_json(tmp_path, capsys):
    artifact_path = tmp_path / "runtime-telemetry.json"
    artifact_path.write_text(
        json.dumps(
            {
                "deployment_manifest": {
                    "deployment_id": "mock-gateway-2026-05",
                    "channels": ["telegram"],
                    "runtime": "mock-gateway",
                },
                "traces": [_trace("trace-1", "telegram", "hermes_entry_transform_hook")],
            }
        ),
        encoding="utf-8",
    )

    exit_code = eval_run.main(
        [
            "--experiment",
            "live_runtime_telemetry",
            "--input",
            str(artifact_path),
            "--json",
        ]
    )

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["report_id"] == "live_runtime_telemetry_v1"
    assert output["validation"]["valid"] is True


def test_mock_gateway_telemetry_campaign_emits_validated_runtime_artifact():
    campaign = run_mock_gateway_telemetry_campaign()

    assert campaign["report_id"] == "mock_runtime_telemetry_campaign_v1"
    assert campaign["claim_scope"] == "mock_gateway_runtime_trace_campaign"
    assert campaign["telemetry_report"]["report_id"] == "live_runtime_telemetry_v1"
    assert campaign["telemetry_report"]["validation"]["valid"] is True
    assert campaign["telemetry_report"]["summary"]["trace_count"] >= 3
    assert campaign["summary"]["blocked_output_count"] >= 1
    assert campaign["summary"]["delivered_output_count"] >= 1
    assert "mock-gateway traces are not production telemetry" in campaign["claim_limitations"]
    assert "raw_output" not in json.dumps(campaign["telemetry_report"]["traces"])


def test_eval_run_mock_runtime_telemetry_campaign_outputs_json(capsys):
    exit_code = eval_run.main(
        ["--experiment", "mock_runtime_telemetry_campaign", "--json"]
    )

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["report_id"] == "mock_runtime_telemetry_campaign_v1"
    assert output["telemetry_report"]["validation"]["valid"] is True


def test_eval_run_mock_runtime_telemetry_campaign_writes_output_file(tmp_path, capsys):
    output_path = tmp_path / "mock-runtime-telemetry.json"

    exit_code = eval_run.main(
        [
            "--experiment",
            "mock_runtime_telemetry_campaign",
            "--output",
            str(output_path),
            "--json",
        ]
    )

    assert exit_code == 0
    stdout_report = json.loads(capsys.readouterr().out)
    file_report = json.loads(output_path.read_text(encoding="utf-8"))
    assert stdout_report["report_id"] == "mock_runtime_telemetry_campaign_v1"
    assert file_report == stdout_report


def _trace(trace_id: str, channel: str, path_id: str) -> dict:
    return {
        "trace_id": trace_id,
        "channel": channel,
        "path_id": path_id,
        "events": [
            {
                "event_type": "context_requested",
                "timestamp": "2026-05-24T10:00:00Z",
                "payload": {"context_pack_hash": f"sha256:{'a' * 64}"},
            },
            {
                "event_type": "context_admitted",
                "timestamp": "2026-05-24T10:00:01Z",
                "payload": {"admitted_items": 2, "blocked_items": 0},
            },
            {
                "event_type": "output_reviewed",
                "timestamp": "2026-05-24T10:00:02Z",
                "payload": {"review_status": "allowed", "response_hash": f"sha256:{'b' * 64}"},
            },
            {
                "event_type": "delivery_decision",
                "timestamp": "2026-05-24T10:00:03Z",
                "payload": {"decision": "delivered", "reason_codes": ["allowlist_ok"]},
            },
            {
                "event_type": "chronicle_event",
                "timestamp": "2026-05-24T10:00:04Z",
                "payload": {"event_id": "evt-1", "event_type": "delivery_decision"},
            },
        ],
    }
