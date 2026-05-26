"""Provenance-tracked scientific evidence bundle.

This module assembles already validated evidence artifacts into a hash-tracked
bundle and runs the scientific defensibility gate over the assembled evidence.
It does not create experimental data.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from relic.eval.controlled_benchmark import run_governance_benchmark
from relic.eval.scientific_defensibility import build_scientific_defensibility_report


REPORT_ID = "scientific_evidence_bundle_v1"
CLAIM_SCOPE = "provenance_tracked_evidence_bundle"
REVIEW_DATE = "2026-05-24"
ARTIFACT_SPECS = {
    "live_model_generation_artifact": {
        "report_ids": {"live_model_generation_artifact_v1"},
        "claim_scopes": {"redacted_external_generation_records"},
    },
    "human_annotation_results": {
        "report_ids": {"human_annotation_results_v1"},
        "claim_scopes": {"imported_human_annotation_results"},
    },
    "nonclinical_red_team_results": {
        "report_ids": {"nonclinical_red_team_results_v1"},
        "claim_scopes": {"imported_expert_red_team_results"},
    },
    "longitudinal_pilot_results": {
        "report_ids": {"longitudinal_pilot_results_v1"},
        "claim_scopes": {"imported_nonclinical_pilot_results"},
    },
    "workbench_usability_results": {
        "report_ids": {"workbench_usability_results_v1"},
        "claim_scopes": {"imported_workbench_usability_results"},
    },
    "live_runtime_telemetry": {
        "report_ids": {
            "live_runtime_telemetry_v1",
            "mock_runtime_telemetry_campaign_v1",
        },
        "claim_scopes": {
            "validated_runtime_trace_artifact",
            "mock_gateway_runtime_trace_campaign",
        },
    },
}


def build_scientific_evidence_bundle_from_file(path: Path) -> dict[str, Any]:
    """Load a descriptor JSON file and build a provenance-tracked bundle."""
    with path.open(encoding="utf-8") as handle:
        descriptor = json.load(handle)
    return build_scientific_evidence_bundle(
        descriptor=descriptor,
        descriptor_dir=path.parent,
    )


def build_scientific_evidence_bundle(
    *,
    descriptor: dict[str, Any],
    descriptor_dir: Path,
) -> dict[str, Any]:
    """Assemble artifact files into a defensibility evidence bundle."""
    artifact_entries = descriptor.get("artifacts", {})
    if not isinstance(artifact_entries, dict):
        raise ValueError("descriptor.artifacts must be an object")

    artifact_manifest: list[dict[str, Any]] = []
    evidence_bundle: dict[str, Any] = {
        "governance_benchmark": run_governance_benchmark(),
    }
    errors: list[str] = []

    for artifact_id, spec in ARTIFACT_SPECS.items():
        entry = artifact_entries.get(artifact_id)
        if entry is None:
            errors.append(f"descriptor.artifacts missing required artifact: {artifact_id}")
            continue
        if not isinstance(entry, dict) or "path" not in entry:
            errors.append(f"descriptor.artifacts.{artifact_id} must include path")
            continue

        artifact_path = _resolve_artifact_path(descriptor_dir, entry["path"])
        if not artifact_path.exists():
            errors.append(f"{artifact_id} path does not exist: {artifact_path}")
            continue

        artifact_hash = _hash_file(artifact_path)
        expected_hash = entry.get("sha256")
        if expected_hash is not None and expected_hash != artifact_hash:
            errors.append(f"{artifact_id} sha256 mismatch")
            continue

        with artifact_path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        report_ids = spec["report_ids"]
        claim_scopes = spec["claim_scopes"]
        if payload.get("report_id") not in report_ids:
            errors.append(
                f"{artifact_id} report_id must be one of {sorted(report_ids)}, got {payload.get('report_id')}"
            )
            continue
        if payload.get("claim_scope") not in claim_scopes:
            errors.append(
                f"{artifact_id} claim_scope must be one of {sorted(claim_scopes)}, got {payload.get('claim_scope')}"
            )
            continue
        if payload.get("validation", {}).get("valid") is not True:
            errors.append(f"{artifact_id} validation.valid must be true")
            continue

        evidence_bundle[artifact_id] = payload
        artifact_manifest.append(
            {
                "artifact_id": artifact_id,
                "path": str(artifact_path),
                "sha256": artifact_hash,
                "size_bytes": artifact_path.stat().st_size,
                "loader_report_id": payload.get("report_id"),
            }
        )

    if errors:
        raise ValueError("; ".join(errors))

    gate_report = build_scientific_defensibility_report(evidence_bundle=evidence_bundle)
    return {
        "report_id": REPORT_ID,
        "claim_scope": CLAIM_SCOPE,
        "methodology": {
            "evidence_model": "hash_manifest_plus_claim_readiness_gate",
            "review_date": REVIEW_DATE,
            "bundle_id": descriptor.get("bundle_id"),
            "provenance_basis": [
                "artifact_file_sha256",
                "artifact_report_id",
                "artifact_claim_scope",
                "artifact_validation_flag",
                "scientific_defensibility_gate",
            ],
        },
        "summary": {
            "artifact_file_count": len(artifact_manifest),
            "gate_overall_status": gate_report["overall_status"],
            "blocks_scientific_claims": gate_report["summary"]["blocks_scientific_claims"],
        },
        "artifact_manifest": artifact_manifest,
        "evidence_bundle": evidence_bundle,
        "gate_report": gate_report,
        "validation": {
            "valid": True,
            "checked_rules": [
                "all_required_artifact_paths_present",
                "artifact_file_sha256_matches_descriptor_when_provided",
                "artifact_report_id_matches_expected_type",
                "artifact_claim_scope_matches_expected_scope",
                "artifact_validation_flag_true",
                "scientific_defensibility_gate_executed",
            ],
        },
        "claim_limitations": [
            "hashes prove artifact file integrity, not upstream recruitment or provider execution integrity",
            "the bundle does not create missing experiment data",
            "broad scientific claims remain blocked if the embedded gate blocks them",
        ],
    }


def _resolve_artifact_path(descriptor_dir: Path, raw_path: str) -> Path:
    artifact_path = Path(raw_path)
    if artifact_path.is_absolute():
        return artifact_path
    return descriptor_dir / artifact_path


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"
