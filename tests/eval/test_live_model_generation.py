"""Live-model generation protocol tests."""

from __future__ import annotations

import json

from scripts import eval_run
from relic.eval.live_model_generation import (
    build_live_model_generation_artifact,
    build_live_model_generation_protocol,
    run_live_model_generation_trial,
)


class FakeProvider:
    provider_id = "fake-openai-compatible"
    model_id = "fake-model-2026-05"

    def generate(self, prompt: str, *, metadata: dict) -> dict:
        assert "john@example.com" not in prompt
        assert metadata["scenario_id"]
        return {
            "content": (
                "Allowed boundary response for "
                f"{metadata['condition']} {metadata['scenario_id']} john@example.com"
            ),
            "tokens_used": 12,
            "latency_ms": 4.5,
        }


def test_live_model_generation_protocol_is_redacted_and_claim_scoped():
    report = build_live_model_generation_protocol(max_scenarios=12)

    assert report["report_id"] == "live_model_generation_protocol_v1"
    assert report["claim_scope"] == "live_generation_protocol_preparation"
    assert report["summary"]["scenario_count"] == 12
    assert report["summary"]["planned_request_count"] == 12 * len(report["conditions"])
    assert "no completed external provider run" in report["claim_limitations"]
    assert report["privacy_controls"]["store_raw_outputs"] is False

    request = report["request_manifest"][0]
    assert request["prompt_hash"].startswith("sha256:")
    assert request["redacted_prompt"]
    assert "raw_prompt" not in request
    assert "john@example.com" not in json.dumps(report)


def test_live_model_generation_trial_stores_redacted_outputs_not_raw_provider_text():
    trial = run_live_model_generation_trial(
        provider=FakeProvider(),
        max_scenarios=3,
        conditions=["full_relic_gumi", "generic_memory"],
    )

    assert trial["report_id"] == "live_model_generation_trial_v1"
    assert trial["claim_scope"] == "redacted_live_generation_trial"
    assert trial["summary"]["scenario_count"] == 3
    assert trial["summary"]["request_count"] == 6
    assert trial["summary"]["provider_count"] == 1
    assert trial["provider_manifest"] == [
        {
            "provider_id": "fake-openai-compatible",
            "model_id": "fake-model-2026-05",
        }
    ]

    for record in trial["generation_records"]:
        assert record["response_hash"].startswith("sha256:")
        assert record["redacted_output"]
        assert "raw_output" not in record
        assert "john@example.com" not in json.dumps(record)
        assert record["score"]["condition"] in {"full_relic_gumi", "generic_memory"}


def test_eval_run_live_model_generation_protocol_outputs_json(capsys):
    exit_code = eval_run.main(
        ["--experiment", "live_model_generation_protocol", "--json"]
    )

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["report_id"] == "live_model_generation_protocol_v1"
    assert output["claim_scope"] == "live_generation_protocol_preparation"


def test_live_model_generation_artifact_validates_redacted_external_records():
    protocol = build_live_model_generation_protocol(
        max_scenarios=2,
        conditions=["full_relic_gumi", "generic_memory"],
    )
    records = []
    for request in protocol["request_manifest"]:
        records.append(
            {
                "request_id": request["request_id"],
                "scenario_id": request["scenario_id"],
                "family": request["family"],
                "condition": request["condition"],
                "provider_id": "provider-a",
                "model_id": "model-a-2026-05",
                "prompt_hash": request["prompt_hash"],
                "response_hash": f"sha256:{'a' * 64}",
                "redacted_output": "Allowed boundary response without personal data.",
                "generation_metadata": {
                    "temperature": 0,
                    "max_tokens": 160,
                    "generated_at": "2026-05-24T10:00:00Z",
                },
            }
        )

    artifact = build_live_model_generation_artifact(
        protocol=protocol,
        provider_manifest=[
            {
                "provider_id": "provider-a",
                "model_id": "model-a-2026-05",
                "temperature": 0,
                "max_tokens": 160,
                "provider_version": "2026-05-24",
            }
        ],
        generation_records=records,
    )

    assert artifact["report_id"] == "live_model_generation_artifact_v1"
    assert artifact["claim_scope"] == "redacted_external_generation_records"
    assert artifact["summary"]["provider_count"] == 1
    assert artifact["summary"]["completed_generation_count"] == 4
    assert artifact["summary"]["expected_generation_count"] == 4
    assert artifact["summary"]["completeness_rate"] == 1.0
    assert artifact["validation"]["valid"] is True
    assert artifact["privacy_controls"]["store_raw_outputs"] is False
    assert "raw_output" not in json.dumps(artifact["generation_records"])


def test_live_model_generation_artifact_rejects_raw_or_mismatched_records():
    protocol = build_live_model_generation_protocol(
        max_scenarios=1,
        conditions=["full_relic_gumi"],
    )
    request = protocol["request_manifest"][0]

    try:
        build_live_model_generation_artifact(
            protocol=protocol,
            provider_manifest=[
                {
                    "provider_id": "provider-a",
                    "model_id": "model-a-2026-05",
                    "temperature": 0,
                    "max_tokens": 160,
                }
            ],
            generation_records=[
                {
                    "request_id": request["request_id"],
                    "scenario_id": request["scenario_id"],
                    "family": request["family"],
                    "condition": request["condition"],
                    "provider_id": "provider-a",
                    "model_id": "model-a-2026-05",
                    "prompt_hash": "sha256:wrong",
                    "response_hash": f"sha256:{'b' * 64}",
                    "redacted_output": "john@example.com",
                    "raw_output": "provider raw text",
                    "generation_metadata": {"temperature": 0, "max_tokens": 160},
                }
            ],
        )
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("expected invalid generation artifact to be rejected")

    assert "raw_output" in message
    assert "prompt_hash mismatch" in message
    assert "PII" in message


def test_live_model_generation_artifact_rejects_missing_reproducibility_metadata():
    protocol = build_live_model_generation_protocol(
        max_scenarios=1,
        conditions=["full_relic_gumi"],
    )
    request = protocol["request_manifest"][0]

    try:
        build_live_model_generation_artifact(
            protocol=protocol,
            provider_manifest=[
                {
                    "provider_id": "provider-a",
                    "model_id": "model-a-2026-05",
                    "temperature": 0,
                    "max_tokens": 160,
                }
            ],
            generation_records=[
                {
                    "request_id": request["request_id"],
                    "scenario_id": request["scenario_id"],
                    "family": request["family"],
                    "condition": request["condition"],
                    "provider_id": "provider-a",
                    "model_id": "model-a-2026-05",
                    "prompt_hash": request["prompt_hash"],
                    "response_hash": f"sha256:{'d' * 64}",
                    "redacted_output": "Allowed boundary response.",
                    "generation_metadata": {"temperature": 0, "max_tokens": 160},
                }
            ],
        )
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("expected incomplete reproducibility metadata to be rejected")

    assert "provider_version" in message
    assert "generated_at" in message


def test_eval_run_live_model_generation_artifact_imports_json(tmp_path, capsys):
    protocol = build_live_model_generation_protocol(
        max_scenarios=1,
        conditions=["full_relic_gumi"],
    )
    request = protocol["request_manifest"][0]
    artifact_path = tmp_path / "redacted-generation-artifact.json"
    artifact_path.write_text(
        json.dumps(
            {
                "protocol": protocol,
                "provider_manifest": [
                    {
                        "provider_id": "provider-a",
                        "model_id": "model-a-2026-05",
                        "temperature": 0,
                        "max_tokens": 160,
                        "provider_version": "2026-05-24",
                    }
                ],
                "generation_records": [
                    {
                        "request_id": request["request_id"],
                        "scenario_id": request["scenario_id"],
                        "family": request["family"],
                        "condition": request["condition"],
                        "provider_id": "provider-a",
                        "model_id": "model-a-2026-05",
                        "prompt_hash": request["prompt_hash"],
                        "response_hash": f"sha256:{'c' * 64}",
                        "redacted_output": "Allowed boundary response.",
                        "generation_metadata": {
                            "temperature": 0,
                            "max_tokens": 160,
                            "generated_at": "2026-05-24T10:00:00Z",
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    exit_code = eval_run.main(
        [
            "--experiment",
            "live_model_generation_artifact",
            "--input",
            str(artifact_path),
            "--json",
        ]
    )

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["report_id"] == "live_model_generation_artifact_v1"
    assert output["validation"]["valid"] is True
