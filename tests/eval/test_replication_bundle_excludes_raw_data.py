"""Tests for replication bundle excluding raw data (PR09).

These tests verify that replication bundles:
1. Exclude raw private data (PII, actual names, addresses, etc.)
2. Use only redacted placeholders
3. Can be validated for privacy compliance
"""

import pytest
import json
import zipfile
from pathlib import Path

from relic.eval.replication_bundle import (
    ReplicationBundle,
    TraceEntry,
    build_bundle,
    create_trace_entry,
)
from relic.replication.bundle import (
    create_replication_bundle,
    validate_bundle_excludes_raw_data,
    verify_bundle_checksums,
    get_bundle_summary,
)


class TestBundleExcludesRawData:
    """Tests for bundle excluding raw private data."""

    def test_redacted_bundle_passes_validation(self):
        """Bundle with redacted content passes validation."""
        traces = [
            create_trace_entry(
                scenario_id="test_1",
                prompt="[REDACTED_EMAIL] preference for [PRIVATE_FACT]",
                response="Your preference has been noted.",
            ),
            create_trace_entry(
                scenario_id="test_2",
                prompt="User asks about [REDACTED_PERSONAL]",
                response="I recall your [REDACTED_DETAIL].",
            ),
        ]

        bundle = ReplicationBundle(
            bundle_id="test_bundle",
            created_at="2024-01-01T00:00:00Z",
            traces=traces,
        )

        is_valid, warnings = validate_bundle_excludes_raw_data(bundle)

        assert is_valid is True
        assert len(warnings) == 0

    def test_bundle_with_email_fails_validation(self):
        """Bundle with raw email fails validation."""
        traces = [
            create_trace_entry(
                scenario_id="test_1",
                prompt="What's my email?",
                response="Your email is john.smith@example.com",
            ),
        ]

        bundle = ReplicationBundle(
            bundle_id="test_bundle",
            created_at="2024-01-01T00:00:00Z",
            traces=traces,
        )

        is_valid, warnings = validate_bundle_excludes_raw_data(bundle)

        assert is_valid is False
        assert len(warnings) > 0

    def test_bundle_with_phone_fails_validation(self):
        """Bundle with raw phone number fails validation."""
        traces = [
            create_trace_entry(
                scenario_id="test_1",
                prompt="What's my phone?",
                response="Your number is 555-123-4567",
            ),
        ]

        bundle = ReplicationBundle(
            bundle_id="test_bundle",
            created_at="2024-01-01T00:00:00Z",
            traces=traces,
        )

        is_valid, warnings = validate_bundle_excludes_raw_data(bundle)

        assert is_valid is False
        assert len(warnings) > 0

    def test_bundle_with_ssn_fails_validation(self):
        """Bundle with SSN fails validation."""
        traces = [
            create_trace_entry(
                scenario_id="test_1",
                prompt="What's my SSN?",
                response="Your SSN is 123-45-6789",
            ),
        ]

        bundle = ReplicationBundle(
            bundle_id="test_bundle",
            created_at="2024-01-01T00:00:00Z",
            traces=traces,
        )

        is_valid, warnings = validate_bundle_excludes_raw_data(bundle)

        assert is_valid is False
        # Check that the response triggered a warning about SSN pattern
        assert len(warnings) > 0

    def test_bundle_with_address_fails_validation(self):
        """Bundle with address fails validation."""
        traces = [
            create_trace_entry(
                scenario_id="test_1",
                prompt="What's my address?",
                response="You live at 123 Main Street.",
            ),
        ]

        bundle = ReplicationBundle(
            bundle_id="test_bundle",
            created_at="2024-01-01T00:00:00Z",
            traces=traces,
        )

        is_valid, warnings = validate_bundle_excludes_raw_data(bundle)

        assert is_valid is False

    def test_bundle_with_credit_card_fails_validation(self):
        """Bundle with credit card fails validation."""
        traces = [
            create_trace_entry(
                scenario_id="test_1",
                prompt="What's my card?",
                response="Card number: 4111-1111-1111-1111",
            ),
        ]

        bundle = ReplicationBundle(
            bundle_id="test_bundle",
            created_at="2024-01-01T00:00:00Z",
            traces=traces,
        )

        is_valid, warnings = validate_bundle_excludes_raw_data(bundle)

        assert is_valid is False


class TestCreateReplicationBundle:
    """Tests for create_replication_bundle helper."""

    def test_create_bundle_from_scenarios(self):
        """Create bundle from scenario list."""
        scenarios = [
            {
                "scenario_id": "mp1",
                "prompt": "[A5] Your preference for dark mode",
                "response": "Noted and updated.",
                "metadata": {"scenario_type": "memory_positive"},
            },
            {
                "scenario_id": "mp2",
                "prompt": "[A5] Your name is Alice",
                "response": "Acknowledged, Alice.",
            },
        ]

        bundle = create_replication_bundle(scenarios)

        assert bundle.bundle_id.startswith("replication_bundle_")
        assert len(bundle.traces) == 2
        assert bundle.traces[0].scenario_id == "mp1"
        assert bundle.traces[0].metadata["scenario_type"] == "memory_positive"

    def test_create_bundle_with_custom_id(self):
        """Create bundle with custom ID."""
        scenarios = [
            {
                "scenario_id": "test_1",
                "prompt": "Test prompt",
                "response": "Test response",
            }
        ]

        bundle = create_replication_bundle(scenarios, bundle_id="custom_bundle_id")

        assert bundle.bundle_id == "custom_bundle_id"

    def test_create_bundle_with_policy(self):
        """Create bundle with policy snapshot."""
        scenarios = [
            {
                "scenario_id": "test_1",
                "prompt": "Test prompt",
                "response": "Test response",
            }
        ]

        policy = {
            "privacy_policy": "strict",
            "correction_enabled": True,
        }

        bundle = create_replication_bundle(
            scenarios,
            include_policy=True,
            policy_snapshot=policy,
        )

        assert bundle.policy_snapshot == policy
        assert bundle.manifest["has_policy_snapshot"] is True


class TestVerifyBundleChecksums:
    """Tests for bundle checksum verification."""

    def test_verify_valid_checksums(self):
        """Verify checksums for valid bundle."""
        traces = [
            create_trace_entry("test_1", "Prompt 1", "Response 1"),
            create_trace_entry("test_2", "Prompt 2", "Response 2"),
        ]

        bundle = build_bundle(traces=traces)
        verification = verify_bundle_checksums(bundle)

        assert verification["test_1"] is True
        assert verification["test_2"] is True
        assert all(verification.values())

    def test_verify_invalid_checksum_fails(self):
        """Invalid checksum detection works."""
        trace = TraceEntry(
            scenario_id="test_1",
            prompt="Prompt 1",
            response="Response 1",
            checksum="invalid_checksum",
        )

        bundle = ReplicationBundle(
            bundle_id="test",
            created_at="2024-01-01",
            traces=[trace],
        )

        verification = verify_bundle_checksums(bundle)

        assert verification["test_1"] is False


class TestBundleSummary:
    """Tests for bundle summary generation."""

    def test_bundle_summary_contains_required_fields(self):
        """Bundle summary has required fields."""
        traces = [
            create_trace_entry("test_1", "Prompt", "Response"),
        ]

        bundle = build_bundle(traces=traces)
        summary = get_bundle_summary(bundle)

        assert "bundle_id" in summary
        assert "created_at" in summary
        assert "trace_count" in summary
        assert "has_policy_snapshot" in summary
        assert "all_checksums_valid" in summary

    def test_bundle_summary_checksums_valid(self):
        """Summary reports correct checksum status."""
        traces = [
            create_trace_entry("test_1", "Prompt", "Response"),
        ]

        bundle = build_bundle(traces=traces)
        summary = get_bundle_summary(bundle)

        assert summary["all_checksums_valid"] is True
        assert summary["trace_count"] == 1


class TestBundleRoundtrip:
    """Tests for bundle roundtrip (create -> save -> load)."""

    def test_bundle_to_zip_excludes_raw_data(self, tmp_path):
        """Bundle ZIP contains no raw data."""
        scenarios = [
            {
                "scenario_id": "mp1",
                "prompt": "[A5] Your preference for dark mode is noted",
                "response": "Noted.",
                "metadata": {"redacted": True},
            }
        ]

        bundle = create_replication_bundle(scenarios)
        zip_path = tmp_path / "test_bundle.zip"
        bundle.to_zip(zip_path)

        assert zip_path.exists()

        # Read ZIP contents
        with zipfile.ZipFile(zip_path, "r") as zf:
            manifest = json.loads(zf.read("manifest.json"))
            traces = json.loads(zf.read("traces.jsonl"))

            assert manifest["bundle_id"] == bundle.bundle_id
            assert len(traces) == 1
            assert traces[0]["scenario_id"] == "mp1"

            # Verify no raw data in traces
            traces_text = json.dumps(traces)
            assert "john.smith" not in traces_text.lower()
            assert "555-123-4567" not in traces_text


class TestPrivacyCompliance:
    """Tests for privacy compliance in bundles."""

    def test_redaction_patterns_are_safe(self):
        """Redaction patterns don't leak data."""
        safe_patterns = [
            "[REDACTED_EMAIL]",
            "[REDACTED_PHONE]",
            "[REDACTED_SSN]",
            "[REDACTED_ADDRESS]",
            "[REDACTED_CREDIT_CARD]",
            "[PRIVATE_FACT]",
            "[PERSONAL_PREFERENCE]",
        ]

        traces = [
            create_trace_entry(
                scenario_id=f"test_{i}",
                prompt=f"Prompt with {pattern}",
                response=f"Response with {pattern}",
            )
            for i, pattern in enumerate(safe_patterns)
        ]

        bundle = ReplicationBundle(
            bundle_id="test",
            created_at="2024-01-01",
            traces=traces,
        )

        is_valid, warnings = validate_bundle_excludes_raw_data(bundle)

        # Should be valid - redaction patterns don't match raw data patterns
        assert is_valid is True

    def test_mixed_content_validation(self):
        """Bundle with mixed content validated correctly."""
        traces = [
            create_trace_entry(
                scenario_id="clean_1",
                prompt="[REDACTED_EMAIL] preference",
                response="Noted.",
            ),
            create_trace_entry(
                scenario_id="raw_1",
                prompt="What's my email?",
                response="Your email is john@example.com",  # Raw data!
            ),
        ]

        bundle = ReplicationBundle(
            bundle_id="test",
            created_at="2024-01-01",
            traces=traces,
        )

        is_valid, warnings = validate_bundle_excludes_raw_data(bundle)

        # Should fail due to raw_1
        assert is_valid is False
        assert any("raw_1" in w for w in warnings)
