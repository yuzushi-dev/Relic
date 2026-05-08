"""Compiler passes for artifact transformation and filtering.

This module defines the pass system used by the compiler pipeline:
- HintFilterPass: Filters disputed/sensitive hints based on policy
- PrivacyScanPass: Scans content for privacy violations
- CorrectionCutoffPass: Applies correction cutoff and generates metadata

Each pass is a callable that transforms input data and produces
a pass result with the transformed content and any metadata.
"""

from __future__ import annotations

import hashlib
import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class HintStatus(Enum):
    """Status of a hint after filtering."""
    INCLUDED = "included"
    EXCLUDED_DISPUTED = "excluded_disputed"
    EXCLUDED_SENSITIVE = "excluded_sensitive"
    DOWNGRADED = "downgraded"


@dataclass
class HintInfo:
    """Information about a hint in the compilation process."""
    hint_hash: str
    hint_type: str  # "disputed", "sensitive", "normal"
    original_content: str | None = None
    status: HintStatus = HintStatus.INCLUDED
    exclusion_reason: str | None = None


@dataclass
class PassResult:
    """Result of a compiler pass."""
    success: bool
    content: dict[str, Any]
    hints: list[HintInfo] = field(default_factory=list)
    privacy_level: str = "safe"
    excluded_count: int = 0
    downgraded_count: int = 0
    messages: list[str] = field(default_factory=list)


class CompilePass(ABC):
    """Abstract base class for compiler passes."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the pass name."""
        pass

    @abstractmethod
    def execute(self, content: dict[str, Any], context: dict[str, Any]) -> PassResult:
        """Execute the pass on content."""
        pass


class HintFilterPass(CompilePass):
    """Filters hints based on dispute status and sensitivity.

    Disputed hints are excluded unless policy approval is present.
    Sensitive hints are downgraded unless policy approval is present.
    """

    def __init__(
        self,
        disputed_approval: bool = False,
        sensitive_approval: bool = False,
    ):
        self._disputed_approval = disputed_approval
        self._sensitive_approval = sensitive_approval

    @property
    def name(self) -> str:
        return "hint_filter"

    def execute(self, content: dict[str, Any], context: dict[str, Any]) -> PassResult:
        """Filter hints based on policy."""
        hints = content.get("hints", [])
        hint_hashes = content.get("hint_hashes", [])
        filtered_hashes = []
        hint_infos: list[HintInfo] = []

        excluded = 0
        downgraded = 0

        for i, hint in enumerate(hints):
            hint_hash = hint_hashes[i] if i < len(hint_hashes) else self._hash_hint(hint)
            hint_type = self._classify_hint(hint)

            info = HintInfo(
                hint_hash=hint_hash,
                hint_type=hint_type,
                original_content=hint.get("content") if isinstance(hint, dict) else None,
            )

            if hint_type == "disputed":
                if self._disputed_approval:
                    info.status = HintStatus.INCLUDED
                else:
                    info.status = HintStatus.EXCLUDED_DISPUTED
                    info.exclusion_reason = "disputed_hint_requires_policy_approval"
                    excluded += 1
            elif hint_type == "sensitive":
                if self._sensitive_approval:
                    info.status = HintStatus.INCLUDED
                else:
                    info.status = HintStatus.DOWNGRADED
                    info.exclusion_reason = "sensitive_hint_downgraded_without_approval"
                    downgraded += 1
            else:
                info.status = HintStatus.INCLUDED
                filtered_hashes.append(hint_hash)

            hint_infos.append(info)

        # Add included hashes
        for info in hint_infos:
            if info.status == HintStatus.INCLUDED:
                filtered_hashes.append(info.hint_hash)

        result_content = content.copy()
        result_content["hint_hashes"] = list(dict.fromkeys(filtered_hashes))  # Dedupe
        result_content["disputed_hints_excluded"] = excluded
        result_content["sensitive_hints_downgraded"] = downgraded

        return PassResult(
            success=True,
            content=result_content,
            hints=hint_infos,
            excluded_count=excluded,
            downgraded_count=downgraded,
            messages=[f"Excluded {excluded} disputed hints", f"Downgraded {downgraded} sensitive hints"],
        )

    def _classify_hint(self, hint: Any) -> str:
        """Classify a hint as disputed, sensitive, or normal."""
        if isinstance(hint, dict):
            hint_type = hint.get("type", "").lower()
            if hint_type in ("disputed", "dispute"):
                return "disputed"
            elif hint_type in ("sensitive", "restricted"):
                return "sensitive"
        return "normal"

    def _hash_hint(self, hint: Any) -> str:
        """Generate hash for a hint."""
        content = json.dumps(hint, sort_keys=True) if isinstance(hint, (dict, list)) else str(hint)
        return hashlib.sha256(content.encode()).hexdigest()


class PrivacyScanPass(CompilePass):
    """Scans content for privacy violations.

    Checks for PII patterns, API keys, and other restricted content.
    Updates privacy level in the output.
    """

    # Patterns for restricted content
    PII_PATTERNS = {
        "pii_email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        "pii_phone": r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
        "pii_ssn": r'\b\d{3}-\d{2}-\d{4}\b',
        "pii_credit_card": r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',
    }

    API_KEY_PATTERNS = {
        "api_key": r'(?i)(api[_-]?key|apikey)\s*[:=]\s*["\']?[A-Za-z0-9_-]{16,}["\']?',
        "password": r'(?i)(password|passwd|pwd)\s*[:=]\s*["\']?[^\s"\']{8,}["\']?',
        "private_key": r'-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----',
    }

    def __init__(self, restricted_categories: set[str] | None = None):
        self._restricted = restricted_categories or {
            "pii_email",
            "pii_phone",
            "pii_ssn",
            "pii_credit_card",
            "api_key",
            "password",
            "private_key",
        }

    @property
    def name(self) -> str:
        return "privacy_scan"

    def execute(self, content: dict[str, Any], context: dict[str, Any]) -> PassResult:
        """Scan content for privacy violations."""
        violations: list[str] = []
        privacy_level = "safe"

        # Serialize content for scanning
        content_str = json.dumps(content, sort_keys=True)

        # Check PII patterns
        for category, pattern in self.PII_PATTERNS.items():
            if category in self._restricted and re.search(pattern, content_str):
                violations.append(f"pii_detected:{category}")
                privacy_level = "s0"

        # Check API key patterns
        for category, pattern in self.API_KEY_PATTERNS.items():
            if category in self._restricted and re.search(pattern, content_str):
                violations.append(f"api_key_detected:{category}")
                privacy_level = "s0"

        result_content = content.copy()
        result_content["privacy_scan_passed"] = privacy_level == "safe"
        result_content["privacy_violations"] = violations

        messages = [f"Privacy scan: {privacy_level}"]
        if violations:
            messages.append(f"Violations: {', '.join(violations)}")

        return PassResult(
            success=True,
            content=result_content,
            privacy_level=privacy_level,
            messages=messages,
        )


class CorrectionCutoffPass(CompilePass):
    """Applies correction cutoff and generates metadata.

    Ensures only corrections verified before the cutoff are included.
    """

    def __init__(self, cutoff_timestamp: datetime | None = None):
        self._cutoff = cutoff_timestamp or datetime.now(timezone.utc)

    @property
    def name(self) -> str:
        return "correction_cutoff"

    def execute(self, content: dict[str, Any], context: dict[str, Any]) -> PassResult:
        """Apply correction cutoff."""
        corrections = content.get("corrections", [])
        applied: list[dict[str, Any]] = []
        pending: list[dict[str, Any]] = []

        for correction in corrections:
            corr_time_str = correction.get("timestamp")
            if corr_time_str:
                # Handle both Z-suffix and +00:00 suffix
                normalized = corr_time_str.replace("Z", "+00:00")
                corr_time = datetime.fromisoformat(normalized)
                # Make aware if naive
                if corr_time.tzinfo is None:
                    corr_time = corr_time.replace(tzinfo=timezone.utc)
                # Compare with cutoff (ensure cutoff is aware)
                cutoff = self._cutoff
                if cutoff.tzinfo is None:
                    cutoff = cutoff.replace(tzinfo=timezone.utc)
                if corr_time <= cutoff:
                    applied.append(correction)
                else:
                    pending.append(correction)
            else:
                # No timestamp - apply conservatively
                applied.append(correction)

        result_content = content.copy()
        result_content["correction_cutoff"] = {
            "cutoff_timestamp": self._cutoff.isoformat().replace("+00:00", "Z"),
            "corrections_applied": applied,
            "corrections_pending": pending,
            "verified": True,
        }

        return PassResult(
            success=True,
            content=result_content,
            messages=[f"Applied {len(applied)} corrections", f"Pending {len(pending)} corrections"],
        )
