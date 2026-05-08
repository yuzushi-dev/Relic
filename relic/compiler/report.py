"""Compiler report generation for audit and debugging.

This module generates reports that explain:
- Which hints were excluded and why
- Which policy gates were applied
- Overall compilation statistics
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from relic.compiler.passes import HintInfo


class ExclusionReason(Enum):
    """Reasons for hint exclusion."""
    DISPUTED = "disputed_hint_requires_policy_approval"
    SENSITIVE = "sensitive_hint_downgraded_without_approval"
    PRIVACY_VIOLATION = "privacy_violation_detected"
    MISSING_APPROVAL = "required_approval_missing"


class PolicyGate(Enum):
    """Policy gates applied during compilation."""
    HINT_FILTER = "hint_filter_gate"
    PRIVACY_SCAN = "privacy_scan_gate"
    CORRECTION_CUTOFF = "correction_cutoff_gate"
    LINEAGE_VERIFICATION = "lineage_verification_gate"
    REPRODUCIBILITY_CHECK = "reproducibility_check_gate"


@dataclass
class ExcludedHint:
    """Record of an excluded hint."""
    hint_hash: str
    exclusion_reason: str
    hint_type: str | None = None
    original_content_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "hint_hash": self.hint_hash,
            "exclusion_reason": self.exclusion_reason,
            "hint_type": self.hint_type,
            "original_content_hash": self.original_content_hash,
        }

    @classmethod
    def from_hint_info(cls, info: HintInfo) -> ExcludedHint:
        """Create from HintInfo."""
        return cls(
            hint_hash=info.hint_hash,
            exclusion_reason=info.exclusion_reason or "unknown",
            hint_type=info.hint_type,
            original_content_hash=info.hint_hash,  # Hash serves as content reference
        )


@dataclass
class PolicyGateResult:
    """Result of applying a policy gate."""
    gate: PolicyGate
    passed: bool
    details: str
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "gate": self.gate.value,
            "passed": self.passed,
            "details": self.details,
            "timestamp": self.timestamp.isoformat() + "Z",
        }


@dataclass
class CompilerReport:
    """Complete compiler report for an artifact compilation.

    This report provides full auditability of the compilation process:
    - Excluded hints with reasons
    - Policy gates applied and their results
    - Compilation statistics
    """
    artifact_id: str
    artifact_type: str
    checksum: str
    lineage_verified: bool = True
    excluded_hints: list[ExcludedHint] = field(default_factory=list)
    downgraded_hints: list[ExcludedHint] = field(default_factory=list)
    policy_gates: list[PolicyGateResult] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    statistics: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_excluded_hint(self, hint: ExcludedHint) -> None:
        """Add an excluded hint."""
        self.excluded_hints.append(hint)

    def add_downgraded_hint(self, hint: ExcludedHint) -> None:
        """Add a downgraded (sensitive) hint."""
        self.downgraded_hints.append(hint)

    def add_policy_gate(self, gate: PolicyGateResult) -> None:
        """Add a policy gate result."""
        self.policy_gates.append(gate)

    def add_error(self, error: str) -> None:
        """Add an error message."""
        self.errors.append(error)

    def add_warning(self, warning: str) -> None:
        """Add a warning message."""
        self.warnings.append(warning)

    def add_statistic(self, key: str, value: Any) -> None:
        """Add a statistic."""
        self.statistics[key] = value

    def to_dict(self) -> dict[str, Any]:
        """Serialize report to dictionary."""
        return {
            "artifact_id": self.artifact_id,
            "artifact_type": self.artifact_type,
            "checksum": self.checksum,
            "lineage_verified": self.lineage_verified,
            "excluded_hints": [h.to_dict() for h in self.excluded_hints],
            "downgraded_hints": [h.to_dict() for h in self.downgraded_hints],
            "policy_gates": [g.to_dict() for g in self.policy_gates],
            "created_at": self.created_at.isoformat() + "Z",
            "statistics": self.statistics,
            "errors": self.errors,
            "warnings": self.warnings,
        }

    def to_json(self, indent: int | None = 2) -> str:
        """Serialize report to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CompilerReport:
        """Deserialize report from dictionary."""
        excluded = [
            ExcludedHint(**h) for h in data.get("excluded_hints", [])
        ]
        downgraded = [
            ExcludedHint(**h) for h in data.get("downgraded_hints", [])
        ]
        gates = [
            PolicyGateResult(
                gate=PolicyGate(g["gate"]),
                passed=g["passed"],
                details=g["details"],
                timestamp=datetime.fromisoformat(g["timestamp"].replace("Z", "+00:00")),
            )
            for g in data.get("policy_gates", [])
        ]
        return cls(
            artifact_id=data["artifact_id"],
            artifact_type=data["artifact_type"],
            checksum=data["checksum"],
            lineage_verified=data.get("lineage_verified", True),
            excluded_hints=excluded,
            downgraded_hints=downgraded,
            policy_gates=gates,
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
            statistics=data.get("statistics", {}),
            errors=data.get("errors", []),
            warnings=data.get("warnings", []),
        )

    @classmethod
    def from_json(cls, json_str: str) -> CompilerReport:
        """Deserialize report from JSON string."""
        return cls.from_dict(json.loads(json_str))

    def get_summary(self) -> str:
        """Get a human-readable summary."""
        lines = [
            f"Compiler Report: {self.artifact_id}",
            f"Checksum: {self.checksum[:16]}...",
            f"Lineage Verified: {self.lineage_verified}",
            "",
            f"Excluded Hints: {len(self.excluded_hints)}",
        ]
        for hint in self.excluded_hints:
            lines.append(f"  - {hint.hint_hash[:16]}... ({hint.exclusion_reason})")

        lines.append("")
        lines.append(f"Downgraded Hints: {len(self.downgraded_hints)}")
        for hint in self.downgraded_hints:
            lines.append(f"  - {hint.hint_hash[:16]}... ({hint.exclusion_reason})")

        lines.append("")
        lines.append("Policy Gates:")
        for gate in self.policy_gates:
            status = "PASS" if gate.passed else "FAIL"
            lines.append(f"  [{status}] {gate.gate.value}: {gate.details}")

        if self.errors:
            lines.append("")
            lines.append("Errors:")
            for err in self.errors:
                lines.append(f"  - {err}")

        if self.warnings:
            lines.append("")
            lines.append("Warnings:")
            for warn in self.warnings:
                lines.append(f"  - {warn}")

        return "\n".join(lines)
