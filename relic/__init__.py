"""relic - local-first knowledge retrieval assistant."""

from __future__ import annotations

from importlib import import_module
from typing import Any

__version__ = "0.1.0"

_EXPORTS: dict[str, str] = {
    # Persistence
    "MemoryBlock": "relic.persistence",
    "MemoryPersistence": "relic.persistence",
    "PrivacyLevel": "relic.persistence",
    "PrivacyTrace": "relic.persistence",
    # Privacy Gate
    "FinalOutputPrivacyGate": "relic.privacy_gate",
    "PrivacyPolicy": "relic.privacy_gate",
    "ScanStage": "relic.privacy_gate",
    # Control - Consent
    "ConsentManager": "relic.control.consent",
    "ConsentType": "relic.control.consent",
    "ConsentScope": "relic.control.consent",
    "ConsentDecision": "relic.control.consent",
    # Control - Pause
    "PauseController": "relic.control.pause",
    "PauseState": "relic.control.pause",
    "PauseRecord": "relic.control.pause",
    # Control - Export
    "ExportManager": "relic.control.export",
    "ExportFormat": "relic.control.export",
    "ExportOptions": "relic.control.export",
    "ExportResult": "relic.control.export",
    # Control - Delete
    "DeleteManager": "relic.control.delete",
    "DeleteScope": "relic.control.delete",
    "AffectedArtifact": "relic.control.delete",
    "DeleteDryRunResult": "relic.control.delete",
    "DeleteResult": "relic.control.delete",
    # Control - Incident
    "IncidentReporter": "relic.control.incident",
    "IncidentSeverity": "relic.control.incident",
    "IncidentStatus": "relic.control.incident",
    "IncidentReport": "relic.control.incident",
    "QuarantinedArtifact": "relic.control.incident",
    # Correction
    "CorrectionPropagator": "relic.correction.propagation",
    "CorrectionType": "relic.correction.propagation",
    "CorrectionScope": "relic.correction.propagation",
    "CorrectionEvent": "relic.correction.propagation",
    "CorrectionTrace": "relic.correction.propagation",
    # UI - Contracts
    "LineageRef": "relic.ui",
    "ReviewStatus": "relic.ui",
    "RiskLevel": "relic.ui",
    "ReviewQueueItem": "relic.ui",
    "ResearcherFeedbackEvent": "relic.ui",
    "FeedbackPropagationTrace": "relic.ui",
    "ReviewBurdenMetrics": "relic.ui",
    "ExceptionWorkbenchDefaults": "relic.ui",
    "UI_STATE_ENUM": "relic.ui",
    "UI_STATE_DESCRIPTIONS": "relic.ui",
    # UI - View Models
    "ReviewItemViewModel": "relic.ui",
    "ReviewQueueViewModel": "relic.ui",
    "REDACTED_PLACEHOLDER": "relic.ui",
    "validate_design": "relic.ui",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    if name not in _EXPORTS:
        raise AttributeError(f"module 'relic' has no attribute {name!r}")
    module = import_module(_EXPORTS[name])
    value = getattr(module, name)
    globals()[name] = value
    return value
