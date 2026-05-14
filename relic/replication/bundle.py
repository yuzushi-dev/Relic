"""Replication bundle helper for PR09.

This module provides helper functions for creating and validating
replication bundles that exclude raw private data.
"""

from pathlib import Path
from typing import Any

from relic.eval.replication_bundle import (
    ReplicationBundle,
    TraceEntry,
    build_bundle,
    create_trace_entry,
)


def create_replication_bundle(
    scenarios: list[dict[str, Any]],
    bundle_id: str | None = None,
    output_dir: Path | str | None = None,
    include_policy: bool = True,
    policy_snapshot: dict[str, Any] | None = None,
) -> ReplicationBundle:
    """Create a replication bundle from scenarios.

    All prompts and responses are redacted to avoid privacy leakage.

    Args:
        scenarios: List of scenario dicts with:
            - scenario_id: Unique scenario identifier
            - prompt: Redacted prompt (should use placeholders)
            - response: Redacted response (should use placeholders)
            - metadata: Optional metadata
        bundle_id: Optional bundle identifier
        output_dir: Optional output directory for ZIP export
        include_policy: Whether to include policy snapshot
        policy_snapshot: Optional policy configuration

    Returns:
        ReplicationBundle instance
    """
    traces = []

    for scenario in scenarios:
        scenario_id = scenario.get("scenario_id", "unknown")
        prompt = scenario.get("prompt", "")
        response = scenario.get("response", "")
        metadata = scenario.get("metadata", {})

        trace = create_trace_entry(
            scenario_id=scenario_id,
            prompt=prompt,
            response=response,
            metadata=metadata,
        )
        traces.append(trace)

    # Include policy snapshot if requested
    policy = policy_snapshot if include_policy else None

    bundle = build_bundle(
        traces=traces,
        policy_snapshot=policy,
        bundle_id=bundle_id,
        output_dir=output_dir,
    )

    return bundle


def validate_bundle_excludes_raw_data(bundle: ReplicationBundle) -> tuple[bool, list[str]]:
    """Validate that bundle does not contain raw private data.

    Checks for common PII patterns in prompts and responses.

    Args:
        bundle: ReplicationBundle to validate

    Returns:
        Tuple of (is_valid, list of warnings)
    """
    warnings: list[str] = []
    is_valid = True

    # Patterns that indicate raw private data
    raw_data_patterns = [
        # Email addresses
        r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        # Phone numbers (various formats)
        r"\d{3}[-.\s]?\d{3}[-.\s]?\d{4}",
        r"\+\d{1,3}\s?\d{3}\s?\d{3}\s?\d{4}",
        # Social Security Numbers
        r"\d{3}-\d{2}-\d{4}",
        # Credit card numbers
        r"\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}",
        # Street addresses (simplified)
        r"\d+\s+[A-Za-z]+\s+(Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln)",
        # Names (simplified check for capitalized words)
        r"\b[A-Z][a-z]+\s+[A-Z][a-z]+\b",
    ]

    import re

    for trace in bundle.traces:
        # Check prompt
        for pattern in raw_data_patterns:
            if re.search(pattern, trace.prompt):
                warnings.append(
                    f"Possible raw data in prompt for {trace.scenario_id}: {pattern}"
                )
                is_valid = False

        # Check response
        for pattern in raw_data_patterns:
            if re.search(pattern, trace.response):
                warnings.append(
                    f"Possible raw data in response for {trace.scenario_id}: {pattern}"
                )
                is_valid = False

    return is_valid, warnings


def verify_bundle_checksums(bundle: ReplicationBundle) -> dict[str, bool]:
    """Verify checksums for all traces in bundle.

    Args:
        bundle: ReplicationBundle to verify

    Returns:
        Dictionary mapping scenario_id to verification status
    """
    return bundle.verify_checksums()


def get_bundle_summary(bundle: ReplicationBundle) -> dict[str, Any]:
    """Get summary of bundle contents.

    Args:
        bundle: ReplicationBundle

    Returns:
        Summary dictionary
    """
    verification = bundle.verify_checksums()
    all_valid = all(verification.values())

    return {
        "bundle_id": bundle.bundle_id,
        "created_at": bundle.created_at,
        "trace_count": len(bundle.traces),
        "has_policy_snapshot": bool(bundle.policy_snapshot),
        "has_report": bool(bundle.report),
        "all_checksums_valid": all_valid,
        "checksum_validation": verification,
    }
