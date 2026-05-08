"""Test excluded hints report generation.

This test verifies:
- Report explains excluded hints with reasons
- Report documents policy gates applied
- Report is human-readable
"""

from __future__ import annotations

from relic.compiler.passes import CorrectionCutoffPass, HintFilterPass, PrivacyScanPass
from relic.compiler.pipeline import CompilationContext, CompilerPipeline
from relic.compiler.report import CompilerReport, ExclusionReason, PolicyGate


class TestExcludedHintsReport:
    """Tests for excluded hints reporting."""

    def test_report_documents_excluded_disputed_hints(self):
        """Test that report documents disputed hint exclusions."""
        pipeline = CompilerPipeline()
        pipeline.add_pass(HintFilterPass(disputed_approval=False))
        pipeline.add_pass(PrivacyScanPass())
        pipeline.add_pass(CorrectionCutoffPass())

        context = CompilationContext(
            session_id="report-test-001",
            disputed_approval=False,
        )

        hints = [
            {"content": "disputed_content", "type": "disputed"},
            {"content": "normal_content", "type": "normal"},
        ]

        artifact, report = pipeline.compile_runtime_profile(
            hints=hints,
            context=context,
        )

        # Verify excluded hints are documented
        assert len(report.excluded_hints) == 1, "Should have 1 excluded hint"
        excluded = report.excluded_hints[0]
        assert excluded.hint_type == "disputed"
        assert excluded.exclusion_reason == "disputed_hint_requires_policy_approval"

    def test_report_documents_excluded_sensitive_hints(self):
        """Test that report documents sensitive hint exclusions."""
        pipeline = CompilerPipeline()
        pipeline.add_pass(HintFilterPass(sensitive_approval=False))
        pipeline.add_pass(PrivacyScanPass())
        pipeline.add_pass(CorrectionCutoffPass())

        context = CompilationContext(
            session_id="report-test-002",
            sensitive_approval=False,
        )

        hints = [
            {"content": "sensitive_content", "type": "sensitive"},
        ]

        artifact, report = pipeline.compile_runtime_profile(
            hints=hints,
            context=context,
        )

        # Verify downgraded hints are documented
        assert len(report.downgraded_hints) == 1, "Should have 1 downgraded hint"
        downgraded = report.downgraded_hints[0]
        assert downgraded.hint_type == "sensitive"

    def test_report_documents_all_policy_gates(self):
        """Test that report documents all policy gates applied."""
        pipeline = CompilerPipeline()
        pipeline.add_pass(HintFilterPass())
        pipeline.add_pass(PrivacyScanPass())
        pipeline.add_pass(CorrectionCutoffPass())

        context = CompilationContext(session_id="report-test-003")

        artifact, report = pipeline.compile_runtime_profile(
            hints=[],
            context=context,
        )

        # Verify all three gates are documented
        gate_values = [g.gate.value for g in report.policy_gates]
        assert "hint_filter_gate" in gate_values
        assert "privacy_scan_gate" in gate_values
        assert "correction_cutoff_gate" in gate_values

    def test_report_includes_lineage_verification(self):
        """Test that report includes lineage verification status."""
        pipeline = CompilerPipeline()
        pipeline.add_pass(HintFilterPass())
        pipeline.add_pass(PrivacyScanPass())
        pipeline.add_pass(CorrectionCutoffPass())

        context = CompilationContext(session_id="report-test-004")

        artifact, report = pipeline.compile_runtime_profile(
            hints=[],
            context=context,
        )

        # Lineage should be verified
        assert report.lineage_verified is True
        assert report.checksum == artifact["checksum"]

    def test_report_can_be_serialized_to_json(self):
        """Test that report can be serialized to JSON."""
        pipeline = CompilerPipeline()
        pipeline.add_pass(HintFilterPass())
        pipeline.add_pass(PrivacyScanPass())
        pipeline.add_pass(CorrectionCutoffPass())

        context = CompilationContext(session_id="report-test-005")

        artifact, report = pipeline.compile_runtime_profile(
            hints=[],
            context=context,
        )

        # Serialize and deserialize
        json_str = report.to_json()
        restored = CompilerReport.from_json(json_str)

        # Verify key fields
        assert restored.artifact_id == report.artifact_id
        assert restored.checksum == report.checksum
        assert restored.lineage_verified == report.lineage_verified

    def test_report_get_summary_is_human_readable(self):
        """Test that report summary is human-readable."""
        pipeline = CompilerPipeline()
        pipeline.add_pass(HintFilterPass(disputed_approval=False))
        pipeline.add_pass(PrivacyScanPass())
        pipeline.add_pass(CorrectionCutoffPass())

        context = CompilationContext(
            session_id="report-test-006",
            disputed_approval=False,
        )

        hints = [
            {"content": "disputed", "type": "disputed"},
            {"content": "normal", "type": "normal"},
        ]

        artifact, report = pipeline.compile_runtime_profile(
            hints=hints,
            context=context,
        )

        summary = report.get_summary()

        # Verify summary contains key information
        assert "Compiler Report" in summary
        assert "Checksum" in summary
        assert "Lineage Verified" in summary
        assert "Excluded Hints" in summary
        assert "Policy Gates" in summary

    def test_report_includes_statistics(self):
        """Test that report includes compilation statistics."""
        pipeline = CompilerPipeline()
        pipeline.add_pass(HintFilterPass(disputed_approval=False))
        pipeline.add_pass(PrivacyScanPass())
        pipeline.add_pass(CorrectionCutoffPass())

        context = CompilationContext(session_id="report-test-007")

        hints = [
            {"content": "disputed", "type": "disputed"},
        ]

        artifact, report = pipeline.compile_runtime_profile(
            hints=hints,
            context=context,
        )

        # Verify statistics
        assert "hints_excluded" in report.statistics
        assert "passes_run" in report.statistics
        assert "artifact_type" in report.statistics
        assert report.statistics["hints_excluded"] == 1

    def test_report_documents_errors_and_warnings(self):
        """Test that report can document errors and warnings."""
        report = CompilerReport(
            artifact_id="test-artifact",
            artifact_type="runtime_profile_pack",
            checksum="abc123",
        )

        report.add_error("Test error message")
        report.add_warning("Test warning message")

        # Verify errors and warnings are recorded
        assert len(report.errors) == 1
        assert len(report.warnings) == 1
        assert report.errors[0] == "Test error message"
        assert report.warnings[0] == "Test warning message"

    def test_report_excludes_hints_explanation(self):
        """Test that excluded hints include proper explanations."""
        pipeline = CompilerPipeline()
        pipeline.add_pass(HintFilterPass(disputed_approval=False))

        context = CompilationContext(
            session_id="report-test-008",
            disputed_approval=False,
        )

        hints = [
            {"content": "hint1", "type": "disputed"},
            {"content": "hint2", "type": "disputed"},
            {"content": "hint3", "type": "normal"},
        ]

        artifact, report = pipeline.compile_runtime_profile(
            hints=hints,
            context=context,
        )

        # Verify all disputed hints were excluded
        assert len(report.excluded_hints) == 2

        # Verify each exclusion reason is documented
        for excluded in report.excluded_hints:
            assert excluded.exclusion_reason is not None
            assert len(excluded.exclusion_reason) > 0
            assert excluded.hint_hash is not None


class TestExclusionReason:
    """Tests for ExclusionReason enum."""

    def test_exclusion_reason_values(self):
        """Test ExclusionReason enum values."""
        assert ExclusionReason.DISPUTED.value == "disputed_hint_requires_policy_approval"
        assert ExclusionReason.SENSITIVE.value == "sensitive_hint_downgraded_without_approval"
        assert ExclusionReason.PRIVACY_VIOLATION.value == "privacy_violation_detected"
        assert ExclusionReason.MISSING_APPROVAL.value == "required_approval_missing"


class TestPolicyGate:
    """Tests for PolicyGate enum."""

    def test_policy_gate_values(self):
        """Test PolicyGate enum values."""
        assert PolicyGate.HINT_FILTER.value == "hint_filter_gate"
        assert PolicyGate.PRIVACY_SCAN.value == "privacy_scan_gate"
        assert PolicyGate.CORRECTION_CUTOFF.value == "correction_cutoff_gate"
        assert PolicyGate.LINEAGE_VERIFICATION.value == "lineage_verification_gate"
        assert PolicyGate.REPRODUCIBILITY_CHECK.value == "reproducibility_check_gate"
