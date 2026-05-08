"""Tests for workbench panel separation - UI hard rules enforcement.

Tests verify:
- Each panel has a render() method
- Safety Signals cannot create continuity markers
- Shared Continuity cannot add clinical labels
- Behavior Constraints runtime preview cannot show safety signal family
- Delivery panel cannot expose raw target IDs by default
- Session panel cannot expose raw session keys
- Panel permissions are correct
"""

from __future__ import annotations

import pytest
from uuid import uuid4

from relic.ui.contracts import REDACTED_PLACEHOLDER
from relic.ui.workbench_panels import (
    PANEL_REGISTRY,
    get_all_panels,
    get_panel,
    SubjectOverviewPanel,
    GumiProfilePanel,
    HermesProfilePanel,
    CronProactivityPanel,
    SafetySignalsPanel,
    BehaviorConstraintsPanel,
    SharedContinuityPanel,
    DeliveryAllowlistsPanel,
    SessionResumePanel,
    GumiEvaluationPanel,
    AuditLogPanel,
    ExportsDeleteForgetPanel,
)
from relic.ui.contracts import REDACTED_PLACEHOLDER


class TestPanelRegistry:
    """Test that all 12 panels are registered and accessible."""

    def test_all_12_panels_registered(self):
        """Verify all 12 required panels are in the registry."""
        assert len(PANEL_REGISTRY) == 12

    def test_panel_ids_match_fixture(self):
        """Verify panel IDs match the fixture specification."""
        expected_ids = {
            "subject_overview",
            "gumi_profile",
            "hermes_profile",
            "cron_proactivity",
            "safety_signals",
            "behavior_constraints",
            "shared_continuity",
            "delivery_allowlists",
            "session_resume",
            "gumi_evaluation",
            "audit_log",
            "exports_delete_forget",
        }
        assert set(PANEL_REGISTRY.keys()) == expected_ids


class TestEachPanelHasRenderMethod:
    """Test that each panel has a render() method returning proper structure."""

    @pytest.mark.parametrize("panel_class", [
        SubjectOverviewPanel,
        GumiProfilePanel,
        HermesProfilePanel,
        CronProactivityPanel,
        SafetySignalsPanel,
        BehaviorConstraintsPanel,
        SharedContinuityPanel,
        DeliveryAllowlistsPanel,
        SessionResumePanel,
        GumiEvaluationPanel,
        AuditLogPanel,
        ExportsDeleteForgetPanel,
    ])
    def test_panel_has_render_method(self, panel_class):
        """Each panel must have a render() method."""
        panel = panel_class()
        assert hasattr(panel, "render")
        assert callable(panel.render)

    @pytest.mark.parametrize("panel_class", [
        SubjectOverviewPanel,
        GumiProfilePanel,
        HermesProfilePanel,
        CronProactivityPanel,
        SafetySignalsPanel,
        BehaviorConstraintsPanel,
        SharedContinuityPanel,
        DeliveryAllowlistsPanel,
        SessionResumePanel,
        GumiEvaluationPanel,
        AuditLogPanel,
        ExportsDeleteForgetPanel,
    ])
    def test_render_returns_dict(self, panel_class):
        """Each panel render() must return a dictionary."""
        panel = panel_class()
        result = panel.render()
        assert isinstance(result, dict)

    @pytest.mark.parametrize("panel_class", [
        SubjectOverviewPanel,
        GumiProfilePanel,
        HermesProfilePanel,
        CronProactivityPanel,
        SafetySignalsPanel,
        BehaviorConstraintsPanel,
        SharedContinuityPanel,
        DeliveryAllowlistsPanel,
        SessionResumePanel,
        GumiEvaluationPanel,
        AuditLogPanel,
        ExportsDeleteForgetPanel,
    ])
    def test_render_returns_panel_id_and_title(self, panel_class):
        """Each panel render() must return panel_id and title."""
        panel = panel_class()
        result = panel.render()
        assert "panel_id" in result
        assert "title" in result
        assert result["panel_id"] == panel.panel_id
        assert result["title"] == panel.title

    @pytest.mark.parametrize("panel_class", [
        SubjectOverviewPanel,
        GumiProfilePanel,
        HermesProfilePanel,
        CronProactivityPanel,
        SafetySignalsPanel,
        BehaviorConstraintsPanel,
        SharedContinuityPanel,
        DeliveryAllowlistsPanel,
        SessionResumePanel,
        GumiEvaluationPanel,
        AuditLogPanel,
        ExportsDeleteForgetPanel,
    ])
    def test_render_returns_permissions(self, panel_class):
        """Each panel render() must include permissions_applied."""
        panel = panel_class()
        result = panel.render()
        assert "permissions_applied" in result
        assert isinstance(result["permissions_applied"], list)


class TestSafetySignalsCannotCreateContinuityMarker:
    """UI HARD RULE: Safety Signals cannot create continuity markers."""

    def test_safety_signals_panel_exists(self):
        """Safety Signals panel must exist."""
        panel = get_panel("safety_signals")
        assert panel is not None

    def test_safety_signals_cannot_create_continuity_marker(self):
        """Safety Signals panel CANNOT create continuity markers."""
        panel = SafetySignalsPanel()
        assert hasattr(panel, "can_create_continuity_marker")
        assert panel.can_create_continuity_marker() is False

    def test_safety_signals_forbidden_action_in_render(self):
        """Safety Signals render() must include create_continuity_marker as blocked."""
        panel = SafetySignalsPanel()
        result = panel.render()
        assert "forbidden_actions_blocked" in result["content"]
        assert "create_continuity_marker" in result["content"]["forbidden_actions_blocked"]

    def test_safety_signals_continuity_creation_status_blocked(self):
        """Safety Signals must show continuity_creation_status as BLOCKED."""
        panel = SafetySignalsPanel()
        result = panel.render()
        assert result["content"].get("continuity_creation_status") == "BLOCKED"


class TestSharedContinuityCannotAddClinicalLabels:
    """UI HARD RULE: Shared Continuity cannot add clinical labels."""

    def test_shared_continuity_panel_exists(self):
        """Shared Continuity panel must exist."""
        panel = get_panel("shared_continuity")
        assert panel is not None

    def test_shared_continuity_add_clinical_label_returns_false(self):
        """Shared Continuity add_clinical_label must return False."""
        panel = SharedContinuityPanel()
        assert hasattr(panel, "add_clinical_label")
        result = panel.add_clinical_label(uuid4(), "clinical_term")
        assert result is False

    def test_shared_continuity_forbidden_action_in_render(self):
        """Shared Continuity render() must include add_clinical_label as blocked."""
        panel = SharedContinuityPanel()
        result = panel.render()
        assert "forbidden_actions_blocked" in result["content"]
        assert "add_clinical_label" in result["content"]["forbidden_actions_blocked"]

    def test_shared_continuity_clinical_labels_not_available(self):
        """Shared Continuity must show clinical_labels_available as False."""
        panel = SharedContinuityPanel()
        result = panel.render()
        assert result["content"].get("clinical_labels_available") is False


class TestBehaviorConstraintsNoSignalFamilyLeak:
    """UI HARD RULE: Behavior Constraints runtime preview cannot show safety signal family."""

    def test_behavior_constraints_panel_exists(self):
        """Behavior Constraints panel must exist."""
        panel = get_panel("behavior_constraints")
        assert panel is not None

    def test_behavior_constraints_runtime_preview_excludes_signal_family(self):
        """Runtime preview must not expose signal family."""
        panel = BehaviorConstraintsPanel()
        result = panel.render()
        assert "runtime_preview" in result["content"]
        runtime_preview = result["content"]["runtime_preview"]
        assert runtime_preview.get("signal_family_visible") is False

    def test_behavior_constraints_get_runtime_preview_ignores_include_signal_family(self):
        """get_runtime_preview must always return signal_family_visible=False."""
        panel = BehaviorConstraintsPanel()
        # Even if True is passed, signal family must not be exposed
        result = panel.get_runtime_preview(include_signal_family=True)
        assert result.get("signal_family_visible") is False

    def test_behavior_constraints_forbidden_action_in_render(self):
        """Behavior Constraints render() must include show_signal_family_in_runtime_preview as blocked."""
        panel = BehaviorConstraintsPanel()
        result = panel.render()
        assert "forbidden_actions_blocked" in result["content"]
        assert "show_signal_family_in_runtime_preview" in result["content"]["forbidden_actions_blocked"]


class TestDeliveryPanelNoRawTargetIds:
    """UI HARD RULE: Delivery panel cannot expose raw target IDs by default."""

    def test_delivery_panel_exists(self):
        """Delivery panel must exist."""
        panel = get_panel("delivery_allowlists")
        assert panel is not None

    def test_delivery_panel_target_id_display_mode_redacted(self):
        """Delivery panel must show target_id_display_mode as redacted."""
        panel = DeliveryAllowlistsPanel()
        result = panel.render()
        assert result["content"].get("target_id_display_mode") == "redacted"

    def test_delivery_panel_get_target_id_display_redacts_raw_id(self):
        """get_target_id_display must redact raw target IDs."""
        panel = DeliveryAllowlistsPanel()
        raw_id = "target_12345_abcde"
        display = panel.get_target_id_display(raw_id)
        assert display != raw_id
        assert "[REDACTED]" in display

    def test_delivery_panel_get_target_id_display_handles_none(self):
        """get_target_id_display must handle None gracefully."""
        panel = DeliveryAllowlistsPanel()
        display = panel.get_target_id_display(None)
        assert display == REDACTED_PLACEHOLDER

    def test_delivery_panel_forbidden_action_in_render(self):
        """Delivery panel render() must include show_raw_target_id as blocked."""
        panel = DeliveryAllowlistsPanel()
        result = panel.render()
        assert "forbidden_actions_blocked" in result["content"]
        assert "show_raw_target_id" in result["content"]["forbidden_actions_blocked"]


class TestSessionPanelNoRawSessionKeys:
    """UI HARD RULE: Session panel cannot expose raw session keys."""

    def test_session_panel_exists(self):
        """Session panel must exist."""
        panel = get_panel("session_resume")
        assert panel is not None

    def test_session_panel_session_key_display_mode_redacted(self):
        """Session panel must show session_key_display_mode as redacted."""
        panel = SessionResumePanel()
        result = panel.render()
        assert result["content"].get("session_key_display_mode") == "redacted"

    def test_session_panel_get_session_key_display_redacts_raw_key(self):
        """get_session_key_display must redact raw session keys."""
        panel = SessionResumePanel()
        raw_key = "sk_session_abc123xyz"
        display = panel.get_session_key_display(raw_key)
        assert display != raw_key
        assert "[REDACTED]" in display

    def test_session_panel_get_session_key_display_handles_none(self):
        """get_session_key_display must handle None gracefully."""
        panel = SessionResumePanel()
        display = panel.get_session_key_display(None)
        assert display == REDACTED_PLACEHOLDER

    def test_session_panel_forbidden_action_in_render(self):
        """Session panel render() must include show_raw_session_key as blocked."""
        panel = SessionResumePanel()
        result = panel.render()
        assert "forbidden_actions_blocked" in result["content"]
        assert "show_raw_session_key" in result["content"]["forbidden_actions_blocked"]


class TestPanelPermissionsCorrect:
    """Test that each panel returns correct required permissions."""

    def test_subject_overview_permissions(self):
        """SubjectOverview must require subjects:read."""
        panel = SubjectOverviewPanel()
        perms = panel.get_required_permissions()
        assert "subjects:read" in perms

    def test_gumi_profile_permissions(self):
        """GumiProfile must require gumi:read and profile:read."""
        panel = GumiProfilePanel()
        perms = panel.get_required_permissions()
        assert "gumi:read" in perms
        assert "profile:read" in perms

    def test_hermes_profile_permissions(self):
        """HermesProfile must require hermes:read and profile:read."""
        panel = HermesProfilePanel()
        perms = panel.get_required_permissions()
        assert "hermes:read" in perms
        assert "profile:read" in perms

    def test_cron_proactivity_permissions(self):
        """CronProactivity must require cron:read and runtime:read."""
        panel = CronProactivityPanel()
        perms = panel.get_required_permissions()
        assert "cron:read" in perms
        assert "runtime:read" in perms

    def test_safety_signals_permissions(self):
        """SafetySignals must require safety:read."""
        panel = SafetySignalsPanel()
        perms = panel.get_required_permissions()
        assert "safety:read" in perms

    def test_behavior_constraints_permissions(self):
        """BehaviorConstraints must require constraints:read and policy:read."""
        panel = BehaviorConstraintsPanel()
        perms = panel.get_required_permissions()
        assert "constraints:read" in perms
        assert "policy:read" in perms

    def test_shared_continuity_permissions(self):
        """SharedContinuity must require continuity:read and shared:read."""
        panel = SharedContinuityPanel()
        perms = panel.get_required_permissions()
        assert "continuity:read" in perms
        assert "shared:read" in perms

    def test_delivery_allowlists_permissions(self):
        """DeliveryAllowlists must require delivery:read and allowlist:read."""
        panel = DeliveryAllowlistsPanel()
        perms = panel.get_required_permissions()
        assert "delivery:read" in perms
        assert "allowlist:read" in perms

    def test_session_resume_permissions(self):
        """SessionResume must require session:read and resume:read."""
        panel = SessionResumePanel()
        perms = panel.get_required_permissions()
        assert "session:read" in perms
        assert "resume:read" in perms

    def test_gumi_evaluation_permissions(self):
        """GumiEvaluation must require evaluation:read."""
        panel = GumiEvaluationPanel()
        perms = panel.get_required_permissions()
        assert "evaluation:read" in perms

    def test_audit_log_permissions(self):
        """AuditLog must require audit:read and logs:read."""
        panel = AuditLogPanel()
        perms = panel.get_required_permissions()
        assert "audit:read" in perms
        assert "logs:read" in perms

    def test_exports_delete_forget_permissions(self):
        """ExportsDeleteForget must require exports:read, delete:write, and forget:write."""
        panel = ExportsDeleteForgetPanel()
        perms = panel.get_required_permissions()
        assert "exports:read" in perms
        assert "delete:write" in perms
        assert "forget:write" in perms


class TestGetAllPanels:
    """Test the get_all_panels function."""

    def test_get_all_panels_returns_12_panels(self):
        """get_all_panels must return exactly 12 panels."""
        panels = get_all_panels()
        assert len(panels) == 12

    def test_get_all_panels_in_priority_order(self):
        """Panels must be returned in priority order (1-12)."""
        panels = get_all_panels()
        expected_order = [
            "subject_overview",
            "gumi_profile",
            "hermes_profile",
            "cron_proactivity",
            "safety_signals",
            "behavior_constraints",
            "shared_continuity",
            "delivery_allowlists",
            "session_resume",
            "gumi_evaluation",
            "audit_log",
            "exports_delete_forget",
        ]
        actual_order = [p.panel_id for p in panels]
        assert actual_order == expected_order


class TestGetPanel:
    """Test the get_panel function."""

    def test_get_panel_returns_valid_panel(self):
        """get_panel with valid ID must return panel instance."""
        panel = get_panel("safety_signals")
        assert panel is not None
        assert isinstance(panel, SafetySignalsPanel)

    def test_get_panel_returns_none_for_invalid_id(self):
        """get_panel with invalid ID must return None."""
        panel = get_panel("nonexistent_panel")
        assert panel is None


class TestNoRawDataExposure:
    """Test that panels do not expose raw sensitive data in render output.

    Per contract, panels must NOT expose:
    - Raw session keys
    - Raw target IDs
    - Safety signal labels
    - Clinical terms

    But descriptive labels (e.g., "Subject registry overview") are allowed.
    """

    @pytest.mark.parametrize("panel_class", [
        SubjectOverviewPanel,
        GumiProfilePanel,
        HermesProfilePanel,
        CronProactivityPanel,
        SafetySignalsPanel,
        BehaviorConstraintsPanel,
        SharedContinuityPanel,
        DeliveryAllowlistsPanel,
        SessionResumePanel,
        GumiEvaluationPanel,
        AuditLogPanel,
        ExportsDeleteForgetPanel,
    ])
    def test_no_raw_session_keys_in_render(self, panel_class):
        """Panel render() must not expose raw session keys."""
        panel = panel_class()
        result = panel.render()
        result_str = str(result)
        # Raw session key patterns should not appear (e.g., sk_session_xxx)
        assert "sk_session_" not in result_str
        # session_key_display_mode is allowed (shows redacted status)
        # But raw key values should not appear
        if "session_key" in result_str and "display_mode" not in result_str:
            # Check it's just the display_mode reference, not actual key values
            assert "sk_" not in result_str

    @pytest.mark.parametrize("panel_class", [
        SubjectOverviewPanel,
        GumiProfilePanel,
        HermesProfilePanel,
        CronProactivityPanel,
        SafetySignalsPanel,
        BehaviorConstraintsPanel,
        SharedContinuityPanel,
        DeliveryAllowlistsPanel,
        SessionResumePanel,
        GumiEvaluationPanel,
        AuditLogPanel,
        ExportsDeleteForgetPanel,
    ])
    def test_no_raw_target_ids_in_render(self, panel_class):
        """Panel render() must not expose raw target IDs."""
        panel = panel_class()
        result = panel.render()
        result_str = str(result)
        # Raw target ID patterns should not appear
        assert "target_12345_abcde" not in result_str
        assert "target_id_display" not in result_str or result["content"].get("target_id_display_mode") == "redacted"

    def test_safety_signals_no_signal_labels(self):
        """Safety Signals panel must not expose signal labels."""
        panel = SafetySignalsPanel()
        result = panel.render()
        # Signal family must be redacted
        assert result["content"].get("signal_family") == REDACTED_PLACEHOLDER

    def test_shared_continuity_no_clinical_terms(self):
        """Shared Continuity panel must not expose clinical terms."""
        panel = SharedContinuityPanel()
        result = panel.render()
        # Clinical labels must not be available
        assert result["content"].get("clinical_labels_available") is False

    def test_behavior_constraints_no_signal_family_in_preview(self):
        """Behavior Constraints runtime preview must not show signal family."""
        panel = BehaviorConstraintsPanel()
        result = panel.render()
        runtime_preview = result["content"].get("runtime_preview", {})
        assert runtime_preview.get("signal_family_visible") is False
