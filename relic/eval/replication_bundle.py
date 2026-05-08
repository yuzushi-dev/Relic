"""Replication bundle builder for Relic E2E.

This module creates replication bundles that include:
- Manifest: Summary of bundle contents
- Traces: Evaluation traces with checksums
- Policy snapshot: Current policy configuration
- Report: Evaluation results
"""

import json
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Any


@dataclass
class TraceEntry:
    """Single trace entry for replication."""

    scenario_id: str
    prompt: str
    response: str
    checksum: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "prompt": self.prompt,
            "response": self.response,
            "checksum": self.checksum,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TraceEntry":
        return cls(
            scenario_id=data["scenario_id"],
            prompt=data["prompt"],
            response=data["response"],
            checksum=data["checksum"],
            metadata=data.get("metadata", {}),
        )


@dataclass
class ReplicationBundle:
    """Replication bundle containing traces, manifest, and policy snapshot."""

    bundle_id: str
    created_at: str
    traces: list[TraceEntry] = field(default_factory=list)
    policy_snapshot: dict[str, Any] = field(default_factory=dict)
    manifest: dict[str, Any] = field(default_factory=dict)
    report: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "created_at": self.created_at,
            "traces": [t.to_dict() for t in self.traces],
            "policy_snapshot": self.policy_snapshot,
            "manifest": self.manifest,
            "report": self.report,
        }

    def to_json(self, output_path: Path | str | None = None) -> str:
        """Export bundle as JSON."""
        json_str = json.dumps(self.to_dict(), indent=2, default=str)
        if output_path:
            Path(output_path).write_text(json_str)
        return json_str

    def create_checksum(self, content: str) -> str:
        """Create SHA-256 checksum for content."""
        return sha256(content.encode()).hexdigest()

    def verify_checksums(self) -> dict[str, bool]:
        """Verify all trace checksums.

        Returns dict mapping scenario_id to verification status.
        """
        verification = {}
        for trace in self.traces:
            content = f"{trace.prompt}|{trace.response}"
            expected_checksum = self.create_checksum(content)
            verification[trace.scenario_id] = trace.checksum == expected_checksum
        return verification

    def generate_manifest(self) -> dict[str, Any]:
        """Generate manifest for the bundle."""
        return {
            "bundle_id": self.bundle_id,
            "created_at": self.created_at,
            "trace_count": len(self.traces),
            "has_policy_snapshot": bool(self.policy_snapshot),
            "has_report": bool(self.report),
            "traces_checksum": self.create_checksum(
                json.dumps([t.to_dict() for t in self.traces], sort_keys=True)
            ),
        }

    def to_zip(self, output_path: Path | str) -> Path:
        """Export bundle as a ZIP archive.

        Creates a reproducible ZIP with manifest, traces, policy, and report.
        """
        output_path = Path(output_path)

        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # Add manifest
            manifest_data = json.dumps(self.manifest, indent=2, default=str)
            zf.writestr("manifest.json", manifest_data)

            # Add traces
            traces_data = json.dumps([t.to_dict() for t in self.traces], indent=2, default=str)
            zf.writestr("traces.jsonl", traces_data)

            # Add policy snapshot if present
            if self.policy_snapshot:
                policy_data = json.dumps(self.policy_snapshot, indent=2, default=str)
                zf.writestr("policy_snapshot.json", policy_data)

            # Add report if present
            if self.report:
                report_data = json.dumps(self.report, indent=2, default=str)
                zf.writestr("report.json", report_data)

            # Add checksums verification file
            checksums = {
                "traces": self.manifest.get("traces_checksum", ""),
                "verification": self.verify_checksums(),
            }
            zf.writestr("checksums.json", json.dumps(checksums, indent=2))

        return output_path


def create_trace_entry(
    scenario_id: str,
    prompt: str,
    response: str,
    metadata: dict[str, Any] | None = None,
) -> TraceEntry:
    """Create a trace entry with checksum.

    All prompts and responses are redacted to avoid privacy leakage.
    """
    content = f"{prompt}|{response}"
    checksum = sha256(content.encode()).hexdigest()

    return TraceEntry(
        scenario_id=scenario_id,
        prompt=prompt,
        response=response,
        checksum=checksum,
        metadata=metadata or {},
    )


def build_bundle(
    traces: list[TraceEntry] | None = None,
    policy_snapshot: dict[str, Any] | None = None,
    report: dict[str, Any] | None = None,
    bundle_id: str | None = None,
    output_dir: Path | str | None = None,
) -> ReplicationBundle:
    """Build a replication bundle.

    Args:
        traces: List of trace entries
        policy_snapshot: Current policy configuration
        report: Evaluation report data
        bundle_id: Optional bundle identifier
        output_dir: Optional output directory for ZIP export

    Returns:
        ReplicationBundle instance
    """
    if traces is None:
        traces = []

    if bundle_id is None:
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        bundle_id = f"replication_bundle_{timestamp}"

    now = datetime.utcnow().isoformat() + "Z"

    bundle = ReplicationBundle(
        bundle_id=bundle_id,
        created_at=now,
        traces=traces,
        policy_snapshot=policy_snapshot or {},
        report=report or {},
    )

    # Generate manifest
    bundle.manifest = bundle.generate_manifest()

    # Export if output directory specified
    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        zip_path = output_dir / f"{bundle_id}.zip"
        bundle.to_zip(zip_path)

    return bundle


def load_bundle(bundle_path: Path | str) -> ReplicationBundle:
    """Load a replication bundle from a ZIP file.

    Args:
        bundle_path: Path to the bundle ZIP file

    Returns:
        ReplicationBundle instance
    """
    bundle_path = Path(bundle_path)

    if not bundle_path.exists():
        raise FileNotFoundError(f"Bundle not found: {bundle_path}")

    traces = []
    policy_snapshot = {}
    manifest = {}
    report = {}

    with zipfile.ZipFile(bundle_path, "r") as zf:
        # Load manifest
        if "manifest.json" in zf.namelist():
            manifest = json.loads(zf.read("manifest.json"))

        # Load traces
        if "traces.jsonl" in zf.namelist():
            traces_data = json.loads(zf.read("traces.jsonl"))
            traces = [TraceEntry.from_dict(t) for t in traces_data]

        # Load policy snapshot
        if "policy_snapshot.json" in zf.namelist():
            policy_snapshot = json.loads(zf.read("policy_snapshot.json"))

        # Load report
        if "report.json" in zf.namelist():
            report = json.loads(zf.read("report.json"))

    return ReplicationBundle(
        bundle_id=manifest.get("bundle_id", bundle_path.stem),
        created_at=manifest.get("created_at", ""),
        traces=traces,
        policy_snapshot=policy_snapshot,
        manifest=manifest,
        report=report,
    )
