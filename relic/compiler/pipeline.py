"""Compiler pipeline orchestration.

This module provides the main CompilerPipeline that orchestrates
the compilation of runtime artifacts with all required passes:
- Lineage tracking
- Hint filtering
- Privacy scanning
- Correction cutoff
- Report generation
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from relic.compiler.lineage import LineageTracker
from relic.compiler.passes import (
    CompilePass,
    CorrectionCutoffPass,
    HintFilterPass,
    PassResult,
    PrivacyScanPass,
)
from relic.compiler.replication import ReplicationBundle
from relic.compiler.report import (
    CompilerReport,
    ExcludedHint,
    PolicyGate,
    PolicyGateResult,
)

# Module-level override for deterministic timestamps in tests
_DETERMINISTIC_TIMESTAMP: datetime | None = None


def set_deterministic_timestamp(ts: datetime | None) -> None:
    """Set a deterministic timestamp for testing reproducibility."""
    global _DETERMINISTIC_TIMESTAMP
    _DETERMINISTIC_TIMESTAMP = ts


def get_timestamp() -> datetime:
    """Get current timestamp, using deterministic value if set."""
    if _DETERMINISTIC_TIMESTAMP is not None:
        return _DETERMINISTIC_TIMESTAMP
    return datetime.now(timezone.utc)


@dataclass
class CompilationContext:
    """Context passed through compilation pipeline."""
    session_id: str
    agent_id: str = "relic-compiler"
    agent_version: str = "1.0.0"
    cutoff_timestamp: datetime | None = None
    disputed_approval: bool = False
    sensitive_approval: bool = False
    extra_metadata: dict[str, Any] = field(default_factory=dict)
    # Optional deterministic source snapshot ID for reproducibility
    source_snapshot_id: str | None = None
    # Optional deterministic artifact ID for reproducibility
    artifact_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "agent_version": self.agent_version,
            "cutoff_timestamp": (
                self.cutoff_timestamp.isoformat() + "Z"
                if self.cutoff_timestamp
                else None
            ),
            "disputed_approval": self.disputed_approval,
            "sensitive_approval": self.sensitive_approval,
            "extra_metadata": self.extra_metadata,
        }


class CompilerPipeline:
    """Main compiler pipeline for runtime artifact compilation.

    Orchestrates all compilation passes and generates reports.
    Guarantees:
    - All outputs have checksums
    - All outputs have lineage
    - Excluded hints are documented
    - Policy gates are logged
    """

    def __init__(
        self,
        lineage_tracker: LineageTracker | None = None,
        default_context: CompilationContext | None = None,
    ):
        self._lineage_tracker = lineage_tracker or LineageTracker()
        self._default_context = default_context
        self._passes: list[CompilePass] = []
        self._reports: list[CompilerReport] = []

    @property
    def lineage_tracker(self) -> LineageTracker:
        """Get lineage tracker."""
        return self._lineage_tracker

    def add_pass(self, pass_: CompilePass) -> None:
        """Add a compilation pass."""
        self._passes.append(pass_)

    def compile(
        self,
        content: dict[str, Any],
        artifact_type: str,
        source_snapshot_id: str | None = None,
        context: CompilationContext | None = None,
    ) -> tuple[dict[str, Any], CompilerReport]:
        """Compile content into a runtime artifact.

        Args:
            content: Input content to compile
            artifact_type: Type of artifact (e.g., "runtime_profile_pack")
            source_snapshot_id: ID of source snapshot (optional, generated if not provided)
            context: Compilation context

        Returns:
            Tuple of (compiled artifact, compiler report)
        """
        context = context or self._default_context or CompilationContext(
            session_id=str(uuid.uuid4())
        )

        # Use context source_snapshot_id if available, otherwise generate deterministically
        if source_snapshot_id is None:
            source_snapshot_id = context.source_snapshot_id
        if source_snapshot_id is None:
            source_snapshot_id = str(uuid.uuid4())

        # Use context artifact_id if available, otherwise generate
        artifact_id = context.artifact_id
        if artifact_id is None:
            artifact_id = content.get("id") or str(uuid.uuid4())

        compiled_content = content.copy()

        # Add required metadata including session_id
        compiled_content["id"] = artifact_id
        compiled_content["session_id"] = context.session_id
        compiled_content["source_snapshot_id"] = source_snapshot_id
        # Use cutoff_timestamp from context for deterministic created_at; fall back to wall clock
        _created_at = context.cutoff_timestamp if (context and context.cutoff_timestamp) else get_timestamp().isoformat().replace("+00:00", "Z")
        compiled_content["created_at"] = _created_at if isinstance(_created_at, str) else _created_at.isoformat().replace("+00:00", "Z")

        # Initialize report
        report = CompilerReport(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            checksum="",  # Will be computed at end
        )

        # Add lineage
        lineage = self._lineage_tracker.register(
            artifact_id=artifact_id,
            source_snapshot_id=source_snapshot_id,
            content=compiled_content,
            metadata={
                "session_id": context.session_id,
                "agent_id": context.agent_id,
            },
        )
        report.lineage_verified = True

        # Run passes
        pass_results: list[PassResult] = []
        for pass_ in self._passes:
            result = pass_.execute(compiled_content, context.to_dict())
            pass_results.append(result)
            compiled_content = result.content

            # Update report based on pass type
            if isinstance(pass_, HintFilterPass):
                # Record excluded/downgraded hints
                for hint_info in result.hints:
                    if hint_info.status.value.startswith("excluded_"):
                        report.add_excluded_hint(ExcludedHint.from_hint_info(hint_info))
                    elif hint_info.status.value == "downgraded":
                        report.add_downgraded_hint(ExcludedHint.from_hint_info(hint_info))

                report.add_policy_gate(PolicyGateResult(
                    gate=PolicyGate.HINT_FILTER,
                    passed=result.success,
                    details=f"Excluded {result.excluded_count}, downgraded {result.downgraded_count}",
                ))
                report.add_statistic("hints_excluded", result.excluded_count)
                report.add_statistic("hints_downgraded", result.downgraded_count)

            elif isinstance(pass_, PrivacyScanPass):
                report.add_policy_gate(PolicyGateResult(
                    gate=PolicyGate.PRIVACY_SCAN,
                    passed=result.privacy_level == "safe",
                    details=f"Privacy level: {result.privacy_level}",
                ))

            elif isinstance(pass_, CorrectionCutoffPass):
                report.add_policy_gate(PolicyGateResult(
                    gate=PolicyGate.CORRECTION_CUTOFF,
                    passed=True,
                    details="Correction cutoff applied",
                ))

        # Compute final checksum
        final_checksum = hashlib.sha256(
            json.dumps(compiled_content, sort_keys=True).encode()
        ).hexdigest()
        compiled_content["checksum"] = final_checksum
        report.checksum = final_checksum

        # Add required fields for runtime_profile_pack schema
        compiled_content["schema_version"] = {
            "major": 1,
            "minor": 0,
            "patch": 0,
            "schema_uri": f"https://relic-oss.dev/schemas/{artifact_type}/v1",
        }
        compiled_content["lineage_refs"] = lineage.parent_lineage_refs

        # Add agent info
        compiled_content["agent_id"] = context.agent_id
        compiled_content["agent_version"] = context.agent_version

        # Add statistics
        report.add_statistic("passes_run", len(pass_results))
        report.add_statistic("artifact_type", artifact_type)
        report.add_statistic("source_snapshot", source_snapshot_id)

        self._reports.append(report)
        return compiled_content, report

    def compile_runtime_profile(
        self,
        hints: list[dict[str, Any]],
        corrections: list[dict[str, Any]] | None = None,
        context: CompilationContext | None = None,
    ) -> tuple[dict[str, Any], CompilerReport]:
        """Compile a runtime profile pack artifact.

        This is a convenience method for compiling the primary runtime
        profile pack with all standard passes.
        """
        # Create a copy of hints to avoid modifying the original
        hints_copy = [{"content": h["content"], "type": h["type"]} for h in hints] if hints else []
        corrections_copy = [{"timestamp": c["timestamp"], "correction": c["correction"]} for c in corrections] if corrections else None

        # Set up default passes
        passes = [
            HintFilterPass(
                disputed_approval=context.disputed_approval if context else False,
                sensitive_approval=context.sensitive_approval if context else False,
            ),
            PrivacyScanPass(),
            CorrectionCutoffPass(
                cutoff_timestamp=context.cutoff_timestamp if context else None
            ),
        ]

        # Use context source_snapshot_id if available, otherwise generate deterministically
        source_snapshot_id = None
        if context and context.source_snapshot_id:
            source_snapshot_id = context.source_snapshot_id
        else:
            # Generate deterministic source snapshot ID based on content
            content_for_hash = json.dumps({"hints": hints_copy, "corrections": corrections_copy}, sort_keys=True)
            source_snapshot_id = hashlib.sha256(content_for_hash.encode()).hexdigest()[:32]

        # Create deterministic artifact ID from source snapshot
        artifact_id = None
        if context and context.artifact_id:
            artifact_id = context.artifact_id
        else:
            artifact_id = hashlib.sha256(source_snapshot_id.encode()).hexdigest()[:32]

        # Create new context with deterministic IDs if not provided
        if context:
            # Create a fresh context object to avoid mutation issues
            new_context = CompilationContext(
                session_id=context.session_id,
                agent_id=context.agent_id,
                agent_version=context.agent_version,
                cutoff_timestamp=context.cutoff_timestamp,
                disputed_approval=context.disputed_approval,
                sensitive_approval=context.sensitive_approval,
                extra_metadata=dict(context.extra_metadata) if context.extra_metadata else {},
                source_snapshot_id=source_snapshot_id,
                artifact_id=artifact_id,
            )
        else:
            new_context = CompilationContext(
                session_id=str(uuid.uuid4()),
                source_snapshot_id=source_snapshot_id,
                artifact_id=artifact_id,
            )

        # Create pipeline with passes
        pipeline = CompilerPipeline(
            lineage_tracker=self._lineage_tracker,
            default_context=new_context,
        )
        for pass_ in passes:
            pipeline.add_pass(pass_)

        # Build content with the copied hints
        content: dict[str, Any] = {
            "profile_type": "session",
            "hints": hints_copy,
            "hint_hashes": [],  # Will be populated by HintFilterPass
            "corrections": corrections_copy or [],
            "is_redacted": False,
            "redacted_reason": None,
        }

        return pipeline.compile(
            content=content,
            artifact_type="runtime_profile_pack",
            source_snapshot_id=source_snapshot_id,
            context=new_context,
        )

    def get_reports(self) -> list[CompilerReport]:
        """Get all generated reports."""
        return self._reports.copy()

    def create_replication_bundle(
        self,
        artifacts: list[dict[str, Any]],
        artifact_type: str,
    ) -> ReplicationBundle:
        """Create a replication bundle from compiled artifacts."""
        bundle = ReplicationBundle()

        for artifact in artifacts:
            artifact_id = artifact.get("id", str(uuid.uuid4()))
            bundle.add_artifact(artifact_id, artifact)

            # Find corresponding report
            for report in self._reports:
                if report.artifact_id == artifact_id:
                    bundle.add_report(report)

        return bundle
