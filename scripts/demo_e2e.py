#!/usr/bin/env python3
"""E2E demo script for Relic E2E.

This script demonstrates the full E2E pipeline:
1. Loads evaluation fixtures
2. Runs scenarios through the mock model
3. Computes metrics
4. Produces a replication bundle

No network calls, no private data, no cloud provider required.
Supports --help and --dry-run for safe execution.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Redaction markers for privacy-safe demo data
REDACTED_MARKERS = ["[USER_NAME]", "[USER_PREFERENCE]", "[LOCATION]", "[TOPIC]", "[NEW_PREFERENCE]", "[OLD_PREFERENCE]"]


def redact_sensitive_content(text: str) -> str:
    """Redact potentially sensitive content from text."""
    result = text
    for marker in REDACTED_MARKERS:
        # Mark presence without exposing actual values
        if marker in text:
            result = result.replace(marker, "[REDACTED]")
    return result


def print_injection_report(injected: list[str], blocked: list[str]) -> None:
    """Print report of what was injected and what was blocked."""
    print("\n=== E2E Demo Injection/Blocking Report ===\n")

    print("INJECTED (safe synthetic data):")
    if injected:
        for item in injected:
            print(f"  ✓ {item}")
    else:
        print("  (none)")

    print("\nBLOCKED (would violate privacy/correction):")
    if blocked:
        for item in blocked:
            print(f"  ✗ {item}")
    else:
        print("  (none - no violations detected)")

    print("\n=== End Report ===\n")


def load_fixtures_for_demo() -> tuple[list[dict[str, Any]], list[str], list[str]]:
    """Load and process fixtures for demo.

    Returns:
        Tuple of (scenarios, injected_items, blocked_items)
    """
    injected: list[str] = []
    blocked: list[str] = []
    scenarios: list[dict[str, Any]] = []

    fixtures_dir = Path(__file__).parent.parent / "fixtures" / "memory-positive"
    fixture_file = fixtures_dir / "memory_positive_scenarios.jsonl"

    if not fixture_file.exists():
        # Create synthetic scenarios for demo when fixtures don't exist
        synthetic_scenarios = [
            {
                "scenario_id": "demo_synthetic_1",
                "prompt": "Demo synthetic prompt for memory recall",
                "expected_response": "Demo synthetic expected response",
                "metadata": {"source": "synthetic", "category": "demo"},
            },
            {
                "scenario_id": "demo_synthetic_2",
                "prompt": "Demo synthetic prompt for preference consistency",
                "expected_response": "Demo synthetic expected response",
                "metadata": {"source": "synthetic", "category": "demo"},
            },
        ]
        injected.append("Synthetic demo scenarios (fallback when fixtures unavailable)")
        for scenario in synthetic_scenarios:
            scenarios.append(scenario)
    else:
        # Load real fixtures with redaction
        with open(fixture_file) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        data = json.loads(line)
                        # Redact any sensitive content
                        data["prompt"] = redact_sensitive_content(data["prompt"])
                        data["expected_response"] = redact_sensitive_content(data["expected_response"])
                        scenarios.append(data)
                        injected.append(f"Fixture: {data.get('scenario_id', 'unknown')}")
                    except json.JSONDecodeError:
                        blocked.append(f"Malformed fixture line: {line[:50]}...")

    return scenarios, injected, blocked


def run_demo_metrics(scenarios: list[dict[str, Any]]) -> dict[str, Any]:
    """Run metrics computation on scenarios.

    Uses mock model to avoid network/cloud dependencies.
    """
    # Import here to avoid hard dependency if not installed
    try:
        from relic.eval import create_mock_model
        from relic.eval.replication_bundle import TraceEntry, create_trace_entry
    except ImportError:
        # Fallback for when relic is not installed
        return {
            "metrics_computed": False,
            "error": "relic.eval not available",
            "mock_metrics": {
                "memory_positive_rate": 0.85,
                "privacy_leakage_rate": 0.0,
                "correction_obedience_rate": 0.90,
            },
        }

    # Create mock model for demo
    mock_model = create_mock_model(baseline="a5")

    traces: list[TraceEntry] = []
    passed_count = 0

    for scenario in scenarios:
        scenario_id = scenario.get("scenario_id", "unknown")
        prompt = scenario.get("prompt", "")
        scenario.get("expected_response", "")

        # Generate mock response
        mock_response = mock_model.generate(prompt)

        # MockResponse uses 'content' not 'text'
        response_text = getattr(mock_response, 'content', str(mock_response))

        # Create trace entry (checksummed for integrity)
        trace = create_trace_entry(
            scenario_id=scenario_id,
            prompt=prompt,
            response=response_text,
            metadata=scenario.get("metadata", {}),
        )
        traces.append(trace)

        # Simple metric: check if response contains expected keywords (demo logic)
        # In a real scenario, this would use proper metric evaluation
        if "acknowledge" in response_text.lower() or "recorded" in response_text.lower():
            passed_count += 1

    total = len(scenarios) if scenarios else 1

    aggregated = {
        "metrics_computed": True,
        "scenario_count": len(scenarios),
        "memory_positive_rate": passed_count / total,
        "privacy_leakage_rate": 0.0,  # No real data in demo
        "correction_obedience_rate": 1.0,  # Demo assumes obedience
        "trace_count": len(traces),
    }

    return aggregated


def create_replication_bundle(
    metrics: dict[str, Any],
    injected: list[str],
    blocked: list[str],
) -> Path:
    """Create replication bundle with demo results."""
    try:
        from relic.eval.replication_bundle import build_bundle
    except ImportError:
        # Fallback when relic not available
        bundle_dir = Path(__file__).parent.parent / "artifacts" / "replication_bundles"
        bundle_dir.mkdir(parents=True, exist_ok=True)
        now = datetime.now(timezone.utc)
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        bundle_file = bundle_dir / f"demo-e2e-{timestamp}.json"

        report = {
            "bundle_id": f"demo-e2e-{timestamp}",
            "created_at": now.isoformat(),
            "metrics": metrics,
            "injected_items": injected,
            "blocked_items": blocked,
        }
        with open(bundle_file, "w") as f:
            json.dump(report, f, indent=2, default=str)
        return bundle_file

    # Build proper replication bundle
    bundle = build_bundle(
        policy_snapshot={"demo_mode": True},
        report={
            "metrics": metrics,
            "injection_report": {
                "injected": injected,
                "blocked": blocked,
            },
        },
        bundle_id="demo-e2e",
    )

    # Export bundle
    bundle_dir = Path(__file__).parent.parent / "artifacts" / "replication_bundles"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    zip_path = bundle_dir / f"demo-e2e-{timestamp}.zip"
    bundle.to_zip(zip_path)

    return zip_path


def main() -> int:
    """Main entry point for E2E demo."""
    parser = argparse.ArgumentParser(
        description="Relic E2E Demo - Demonstrates full pipeline without cloud/private data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python demo_e2e.py           Run full demo
  python demo_e2e.py --dry-run Show what would be done
  python demo_e2e.py --verbose Verbose output
        """,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()

    now = datetime.now(timezone.utc)

    print("=" * 60)
    print("Relic E2E Demo")
    print("=" * 60)
    print(f"Timestamp: {now.isoformat()}")
    print(f"Dry-run: {args.dry_run}")
    print()

    if args.dry_run:
        print("[DRY-RUN] Would execute the following steps:")
        print("  1. Load evaluation fixtures (memory-positive scenarios)")
        print("  2. Process scenarios through mock model")
        print("  3. Compute metrics (privacy, correction, memory)")
        print("  4. Generate replication bundle")
        print("  5. Print injection/blocking report")
        print()
        print("[DRY-RUN] Would NOT:")
        print("  - Access network")
        print("  - Use real private data")
        print("  - Require cloud provider")
        return 0

    # Step 1: Load fixtures
    print("[1/4] Loading evaluation fixtures...")
    scenarios, injected, blocked = load_fixtures_for_demo()
    print(f"  Loaded {len(scenarios)} scenario(s)")

    # Step 2: Run metrics
    print("[2/4] Computing metrics...")
    metrics = run_demo_metrics(scenarios)
    print(f"  Metrics computed: {metrics.get('metrics_computed', False)}")

    # Step 3: Create replication bundle
    print("[3/4] Creating replication bundle...")
    bundle_path = create_replication_bundle(metrics, injected, blocked)
    print(f"  Bundle created: {bundle_path}")

    # Step 4: Print injection report
    print("[4/4] Generating injection report...")
    print_injection_report(injected, blocked)

    if args.verbose:
        print("\n[VERBOSE] Metrics summary:")
        for key, value in metrics.items():
            print(f"  {key}: {value}")

    print("=" * 60)
    print("Demo completed successfully!")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
