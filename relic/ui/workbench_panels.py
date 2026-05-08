"""Workbench panel implementations for researcher audit UI.

Each panel enforces zero-knowledge guarantees and UI hard rules:
- Safety Signals cannot create continuity markers.
- Shared Continuity cannot add clinical labels.
- Behavior Constraints runtime preview cannot show safety signal family.
- Delivery panel cannot expose raw target IDs by default.
- Session panel cannot expose raw session keys.

Panels do NOT expose:
- Raw session keys
- Raw target IDs
- Safety signal labels
- Clinical terms
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from relic.ui.contracts import (
    REDACTED_PLACEHOLDER,
    LineageRef,
    ReviewStatus,
)


class WorkbenchPanel(ABC):
    """Base class for all workbench panels.

    All panels enforce:
    - Redacted-by-default for sensitive data
    - Lineage tracking for all visible claims
    - UI hard rules preventing forbidden actions
    """

    panel_id: str = ""
    title: str = ""

    def __init__(self):
        self.panel_id = self.__class__.panel_id
        self.title = self.__class__.title
        self._validate_panel()

    def _validate_panel(self) -> None:
        """Validate panel configuration."""
        assert self.panel_id, "panel_id must be set"
        assert self.title, "title must be set"

    @abstractmethod
    def render(self) -> dict[str, Any]:
        """Render panel content as HTML/JSON representation.

        Returns:
            Dictionary with panel data, ensuring sensitive content is redacted.
        """
        pass

    @abstractmethod
    def get_required_permissions(self) -> list[str]:
        """Return list of permissions needed to view this panel.

        Returns:
            List of permission strings required for panel access.
        """
        pass

    def _create_lineage_ref(
        self,
        artifact_id: UUID,
        artifact_type: str,
        relationship: str,
    ) -> LineageRef:
        """Helper to create lineage references."""
        return LineageRef(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            relationship=relationship,
        )

    def _redact(self, value: str | None, display: str = "[REDACTED]") -> str:
        """Helper to redact sensitive values."""
        if value is None:
            return display
        return display


class SubjectOverviewPanel(WorkbenchPanel):
    """Panel for subject overview - priority 1."""

    panel_id = "subject_overview"
    title = "Subject Overview"

    def render(self) -> dict[str, Any]:
        """Render subject overview panel."""
        return {
            "panel_id": self.panel_id,
            "title": self.title,
            "view_id": str(uuid4()),
            "rendered_at": datetime.utcnow().isoformat(),
            "content": {
                "subjects_summary": "Subject registry overview",
                "total_subjects": REDACTED_PLACEHOLDER,
                "active_sessions": REDACTED_PLACEHOLDER,
                "last_activity": REDACTED_PLACEHOLDER,
            },
            "lineage_refs": [],
            "permissions_applied": self.get_required_permissions(),
        }

    def get_required_permissions(self) -> list[str]:
        return ["subjects:read"]


class GumiProfilePanel(WorkbenchPanel):
    """Panel for Gumi profile - priority 2.

    Enforces: show_safety_signal_as_trait is forbidden.
    """

    panel_id = "gumi_profile"
    title = "Gumi Profile"

    def render(self) -> dict[str, Any]:
        """Render Gumi profile panel."""
        return {
            "panel_id": self.panel_id,
            "title": self.title,
            "view_id": str(uuid4()),
            "rendered_at": datetime.utcnow().isoformat(),
            "content": {
                "profile_summary": "Gumi identity profile overview",
                "active_traits": REDACTED_PLACEHOLDER,
                "runtime_state": REDACTED_PLACEHOLDER,
                # SAFETY SIGNAL LABELS ARE NEVER EXPOSED HERE
                "forbidden_actions_blocked": ["show_safety_signal_as_trait"],
            },
            "lineage_refs": [],
            "permissions_applied": self.get_required_permissions(),
        }

    def get_required_permissions(self) -> list[str]:
        return ["gumi:read", "profile:read"]


class HermesProfilePanel(WorkbenchPanel):
    """Panel for Hermes profile - priority 3.

    Enforces: show_raw_session_key is forbidden.
    """

    panel_id = "hermes_profile"
    title = "Hermes Profile"

    def render(self) -> dict[str, Any]:
        """Render Hermes profile panel."""
        return {
            "panel_id": self.panel_id,
            "title": self.title,
            "view_id": str(uuid4()),
            "rendered_at": datetime.utcnow().isoformat(),
            "content": {
                "profile_summary": "Hermes runtime profile overview",
                "session_count": REDACTED_PLACEHOLDER,
                "active_runtimes": REDACTED_PLACEHOLDER,
                # RAW SESSION KEYS ARE NEVER EXPOSED
                "forbidden_actions_blocked": ["show_raw_session_key"],
            },
            "lineage_refs": [],
            "permissions_applied": self.get_required_permissions(),
        }

    def get_required_permissions(self) -> list[str]:
        return ["hermes:read", "profile:read"]


class CronProactivityPanel(WorkbenchPanel):
    """Panel for Cron & Proactivity - priority 4.

    Enforces: deliver_without_gate is forbidden.
    """

    panel_id = "cron_proactivity"
    title = "Cron & Proactivity"

    def render(self) -> dict[str, Any]:
        """Render Cron & Proactivity panel."""
        return {
            "panel_id": self.panel_id,
            "title": self.title,
            "view_id": str(uuid4()),
            "rendered_at": datetime.utcnow().isoformat(),
            "content": {
                "cron_summary": "Scheduled autonomous events overview",
                "pending_events": REDACTED_PLACEHOLDER,
                "proactivity_metrics": REDACTED_PLACEHOLDER,
                "forbidden_actions_blocked": ["deliver_without_gate"],
            },
            "lineage_refs": [],
            "permissions_applied": self.get_required_permissions(),
        }

    def get_required_permissions(self) -> list[str]:
        return ["cron:read", "runtime:read"]


class SafetySignalsPanel(WorkbenchPanel):
    """Panel for Safety Signals - priority 5.

    UI HARD RULE: Safety Signals cannot create continuity markers.
    This panel CANNOT create memory/continuity markers.
    """

    panel_id = "safety_signals"
    title = "Safety Signals"

    def render(self) -> dict[str, Any]:
        """Render Safety Signals panel.

        SAFETY SIGNAL LABELS are never exposed.
        Continuity marker creation is FORBIDDEN.
        """
        return {
            "panel_id": self.panel_id,
            "title": self.title,
            "view_id": str(uuid4()),
            "rendered_at": datetime.utcnow().isoformat(),
            "content": {
                "signals_summary": "Safety signal overview",
                "active_signals": REDACTED_PLACEHOLDER,
                "signal_family": REDACTED_PLACEHOLDER,  # CLINICAL TERMS NEVER EXPOSED
                "triggered_count": REDACTED_PLACEHOLDER,
                # HARD RULE ENFORCEMENT
                "forbidden_actions_blocked": ["create_continuity_marker"],
                "continuity_creation_status": "BLOCKED",
            },
            "lineage_refs": [],
            "permissions_applied": self.get_required_permissions(),
        }

    def get_required_permissions(self) -> list[str]:
        return ["safety:read"]

    def can_create_continuity_marker(self) -> bool:
        """Safety Signals panel CANNOT create continuity markers."""
        return False


class BehaviorConstraintsPanel(WorkbenchPanel):
    """Panel for Behavior Constraints - priority 6.

    UI HARD RULE: Runtime preview cannot show safety signal family.
    """

    panel_id = "behavior_constraints"
    title = "Behavior Constraints"

    def render(self) -> dict[str, Any]:
        """Render Behavior Constraints panel.

        Runtime preview CANNOT show safety signal family.
        """
        return {
            "panel_id": self.panel_id,
            "title": self.title,
            "view_id": str(uuid4()),
            "rendered_at": datetime.utcnow().isoformat(),
            "content": {
                "constraints_summary": "Behavior constraints overview",
                "active_constraints": REDACTED_PLACEHOLDER,
                "runtime_preview_available": True,
                # SAFETY SIGNAL FAMILY IS NEVER EXPOSED IN RUNTIME PREVIEW
                "runtime_preview": {
                    "allowed_behaviors": REDACTED_PLACEHOLDER,
                    "restricted_behaviors": REDACTED_PLACEHOLDER,
                    "signal_family_visible": False,  # HARD RULE ENFORCEMENT
                },
                "forbidden_actions_blocked": ["show_signal_family_in_runtime_preview"],
            },
            "lineage_refs": [],
            "permissions_applied": self.get_required_permissions(),
        }

    def get_required_permissions(self) -> list[str]:
        return ["constraints:read", "policy:read"]

    def get_runtime_preview(self, include_signal_family: bool = False) -> dict[str, Any]:
        """Get runtime preview with signal family protection.

        Args:
            include_signal_family: If True, signal family will be shown (but this
                parameter is ignored - signal family is NEVER shown per UI hard rule).

        Returns:
            Runtime preview without signal family information.
        """
        return {
            "allowed_behaviors": REDACTED_PLACEHOLDER,
            "restricted_behaviors": REDACTED_PLACEHOLDER,
            "signal_family_visible": False,
            "note": "Safety signal family is redacted from runtime preview per UI hard rule",
        }


class SharedContinuityPanel(WorkbenchPanel):
    """Panel for Shared Continuity - priority 7.

    UI HARD RULE: Shared Continuity cannot add clinical labels.
    """

    panel_id = "shared_continuity"
    title = "Shared Continuity"

    def render(self) -> dict[str, Any]:
        """Render Shared Continuity panel.

        CLINICAL LABELS are never added to continuity markers.
        """
        return {
            "panel_id": self.panel_id,
            "title": self.title,
            "view_id": str(uuid4()),
            "rendered_at": datetime.utcnow().isoformat(),
            "content": {
                "continuity_summary": "Shared continuity markers overview",
                "active_markers": REDACTED_PLACEHOLDER,
                "recent_shared": REDACTED_PLACEHOLDER,
                # CLINICAL LABELS ARE NEVER ADDED
                "forbidden_actions_blocked": ["add_clinical_label"],
                "clinical_labels_available": False,
            },
            "lineage_refs": [],
            "permissions_applied": self.get_required_permissions(),
        }

    def get_required_permissions(self) -> list[str]:
        return ["continuity:read", "shared:read"]

    def add_clinical_label(self, marker_id: UUID, label: str) -> bool:
        """Shared Continuity CANNOT add clinical labels - returns False."""
        return False


class DeliveryAllowlistsPanel(WorkbenchPanel):
    """Panel for Delivery & Allowlists - priority 8.

    UI HARD RULE: Delivery panel cannot expose raw target IDs by default.
    """

    panel_id = "delivery_allowlists"
    title = "Delivery & Allowlists"

    def render(self) -> dict[str, Any]:
        """Render Delivery & Allowlists panel.

        RAW TARGET IDS are never exposed by default.
        """
        return {
            "panel_id": self.panel_id,
            "title": self.title,
            "view_id": str(uuid4()),
            "rendered_at": datetime.utcnow().isoformat(),
            "content": {
                "delivery_summary": "Platform allowlist overview",
                "platforms_configured": REDACTED_PLACEHOLDER,
                "pending_deliveries": REDACTED_PLACEHOLDER,
                # RAW TARGET IDS ARE NEVER EXPOSED
                "forbidden_actions_blocked": ["show_raw_target_id"],
                "target_id_display_mode": "redacted",
            },
            "lineage_refs": [],
            "permissions_applied": self.get_required_permissions(),
        }

    def get_required_permissions(self) -> list[str]:
        return ["delivery:read", "allowlist:read"]

    def get_target_id_display(self, raw_id: str | None) -> str:
        """Get target ID display with redaction protection.

        Args:
            raw_id: The raw target ID.

        Returns:
            Redacted representation, never raw ID.
        """
        if raw_id is None:
            return REDACTED_PLACEHOLDER
        # Target IDs are redacted by default
        return f"target_{hash(raw_id) % 10000:04d} [REDACTED]"


class SessionResumePanel(WorkbenchPanel):
    """Panel for Session & Resume - priority 9.

    UI HARD RULE: Session panel cannot expose raw session keys.
    """

    panel_id = "session_resume"
    title = "Session & Resume"

    def render(self) -> dict[str, Any]:
        """Render Session & Resume panel.

        RAW SESSION KEYS are never exposed.
        """
        return {
            "panel_id": self.panel_id,
            "title": self.title,
            "view_id": str(uuid4()),
            "rendered_at": datetime.utcnow().isoformat(),
            "content": {
                "session_summary": "Session resume reconciliation overview",
                "active_sessions": REDACTED_PLACEHOLDER,
                "pending_resumes": REDACTED_PLACEHOLDER,
                # RAW SESSION KEYS ARE NEVER EXPOSED
                "forbidden_actions_blocked": ["show_raw_session_key"],
                "session_key_display_mode": "redacted",
            },
            "lineage_refs": [],
            "permissions_applied": self.get_required_permissions(),
        }

    def get_required_permissions(self) -> list[str]:
        return ["session:read", "resume:read"]

    def get_session_key_display(self, raw_key: str | None) -> str:
        """Get session key display with redaction protection.

        Args:
            raw_key: The raw session key.

        Returns:
            Redacted representation, never raw key.
        """
        if raw_key is None:
            return REDACTED_PLACEHOLDER
        # Session keys are redacted by default
        return f"session_{hash(raw_key) % 10000:04d} [REDACTED]"


class GumiEvaluationPanel(WorkbenchPanel):
    """Panel for Gumi Evaluation - priority 10."""

    panel_id = "gumi_evaluation"
    title = "Gumi Evaluation"

    def render(self) -> dict[str, Any]:
        """Render Gumi Evaluation panel."""
        return {
            "panel_id": self.panel_id,
            "title": self.title,
            "view_id": str(uuid4()),
            "rendered_at": datetime.utcnow().isoformat(),
            "content": {
                "evaluation_summary": "Gumi evaluation results overview",
                "total_evaluations": REDACTED_PLACEHOLDER,
                "last_evaluation": REDACTED_PLACEHOLDER,
                "performance_metrics": REDACTED_PLACEHOLDER,
            },
            "lineage_refs": [],
            "permissions_applied": self.get_required_permissions(),
        }

    def get_required_permissions(self) -> list[str]:
        return ["evaluation:read"]


class AuditLogPanel(WorkbenchPanel):
    """Panel for Audit Log - priority 11."""

    panel_id = "audit_log"
    title = "Audit Log"

    def render(self) -> dict[str, Any]:
        """Render Audit Log panel."""
        return {
            "panel_id": self.panel_id,
            "title": self.title,
            "view_id": str(uuid4()),
            "rendered_at": datetime.utcnow().isoformat(),
            "content": {
                "log_summary": "System audit log overview",
                "recent_events": REDACTED_PLACEHOLDER,
                "event_types_recorded": REDACTED_PLACEHOLDER,
                "total_entries": REDACTED_PLACEHOLDER,
            },
            "lineage_refs": [],
            "permissions_applied": self.get_required_permissions(),
        }

    def get_required_permissions(self) -> list[str]:
        return ["audit:read", "logs:read"]


class ExportsDeleteForgetPanel(WorkbenchPanel):
    """Panel for Exports / Delete / Forget - priority 12.

    Enforces: export_researcher_only_signals_to_subject is forbidden.
    """

    panel_id = "exports_delete_forget"
    title = "Exports / Delete / Forget"

    def render(self) -> dict[str, Any]:
        """Render Exports / Delete / Forget panel."""
        return {
            "panel_id": self.panel_id,
            "title": self.title,
            "view_id": str(uuid4()),
            "rendered_at": datetime.utcnow().isoformat(),
            "content": {
                "exports_summary": "Data export and deletion operations",
                "recent_exports": REDACTED_PLACEHOLDER,
                "pending_deletions": REDACTED_PLACEHOLDER,
                "forget_operations": REDACTED_PLACEHOLDER,
                "forbidden_actions_blocked": ["export_researcher_only_signals_to_subject"],
            },
            "lineage_refs": [],
            "permissions_applied": self.get_required_permissions(),
        }

    def get_required_permissions(self) -> list[str]:
        return ["exports:read", "delete:write", "forget:write"]


# Registry of all workbench panels
PANEL_REGISTRY: dict[str, type[WorkbenchPanel]] = {
    cls.panel_id: cls
    for cls in [
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
    ]
}


def get_panel(panel_id: str) -> WorkbenchPanel | None:
    """Get panel instance by panel_id.

    Args:
        panel_id: The panel identifier.

    Returns:
        Panel instance or None if not found.
    """
    panel_class = PANEL_REGISTRY.get(panel_id)
    if panel_class is None:
        return None
    return panel_class()


def get_all_panels() -> list[WorkbenchPanel]:
    """Get all workbench panel instances.

    Returns:
        List of all panel instances ordered by priority.
    """
    panels = []
    for cls in [
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
    ]:
        panels.append(cls())
    return panels
