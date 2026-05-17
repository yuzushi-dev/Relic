"""
Source Policy — Unified source-class taxonomy for Hermes adapter.

This module defines a single source-class taxonomy that governs
whether a source is eligible for ingestion as subject evidence.

Design: Hermes provides sources. Relic classifies and governs eligibility.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from relic.hermes_adapter.envelope import HermesRuntimeEnvelope


class SourceClass(str, Enum):
    """Source class taxonomy."""
    USER_DIRECT = "user_direct"
    USER_REQUESTED = "user_requested"
    SYSTEM_GENERATED = "system_generated"
    GUMI_DIEGETIC_EVENT = "gumi_diegetic_event"
    PUBLIC_WEB_SOURCE = "public_web_source"
    TOOL_EXECUTION_RESULT = "tool_execution_result"
    PROACTIVE_DELIVERY = "proactive_delivery"
    ADMIN_OVERRIDE = "admin_override"


class ConsentState(str, Enum):
    """Consent state for source."""
    GRANTED = "granted"
    DENIED = "denied"
    NOT_REQUIRED = "not_required"
    EXPIRED = "expired"


@dataclass(frozen=True)
class SourceClassification:
    """Source classification result."""
    source_class: SourceClass
    is_evidence_eligible: bool
    consent_required: bool = False
    provenance_required: bool = False
    notes: Optional[str] = None


class SourcePolicy:
    """Unified source policy enforcer."""

    def __init__(
        self,
        allow_diegetic_as_evidence: bool = False,
        require_web_provenance: bool = True,
    ):
        self.allow_diegetic_as_evidence = allow_diegetic_as_evidence
        self.require_web_provenance = require_web_provenance

    def classify(self, envelope: HermesRuntimeEnvelope) -> SourceClassification:
        """Classify source from envelope."""
        source_class = self._determine_source_class(envelope)
        is_eligible = self._is_evidence_eligible(source_class)
        consent_required = self._is_consent_required(source_class)
        provenance_required = self._is_provenance_required(source_class)

        return SourceClassification(
            source_class=source_class,
            is_evidence_eligible=is_eligible,
            consent_required=consent_required,
            provenance_required=provenance_required,
        )

    def _determine_source_class(self, envelope: HermesRuntimeEnvelope) -> SourceClass:
        """Determine source class from envelope metadata."""
        if envelope.tool_call_id and "proactive" in envelope.tool_call_id.lower():
            return SourceClass.PROACTIVE_DELIVERY
        if envelope.tool_call_id:
            return SourceClass.TOOL_EXECUTION_RESULT
        if envelope.sender_ref and envelope.platform:
            return SourceClass.USER_DIRECT
        return SourceClass.SYSTEM_GENERATED

    def _is_evidence_eligible(self, source_class: SourceClass) -> bool:
        """Check if source class is eligible for evidence."""
        if source_class in (
            SourceClass.USER_DIRECT,
            SourceClass.USER_REQUESTED,
            SourceClass.SYSTEM_GENERATED,
            SourceClass.TOOL_EXECUTION_RESULT,
            SourceClass.ADMIN_OVERRIDE,
        ):
            return True
        if source_class == SourceClass.GUMI_DIEGETIC_EVENT:
            return self.allow_diegetic_as_evidence
        if source_class == SourceClass.PUBLIC_WEB_SOURCE:
            return False  # Requires explicit user request check
        if source_class == SourceClass.PROACTIVE_DELIVERY:
            return False
        return False

    def _is_consent_required(self, source_class: SourceClass) -> bool:
        """Check if consent is required for source class."""
        if source_class in (
            SourceClass.PUBLIC_WEB_SOURCE,
            SourceClass.GUMI_DIEGETIC_EVENT,
            SourceClass.ADMIN_OVERRIDE,
        ):
            return True
        return False

    def _is_provenance_required(self, source_class: SourceClass) -> bool:
        """Check if provenance must be recorded."""
        if source_class in (
            SourceClass.PUBLIC_WEB_SOURCE,
            SourceClass.TOOL_EXECUTION_RESULT,
            SourceClass.USER_REQUESTED,
            SourceClass.GUMI_DIEGETIC_EVENT,
        ):
            return True
        return False

    def is_evidence_eligible(
        self,
        source_class: SourceClass,
        consent_state: ConsentState,
        is_explicit_request: bool = False,
    ) -> bool:
        """Check if source is eligible for evidence with full context."""
        # Web sources require explicit request
        if source_class == SourceClass.PUBLIC_WEB_SOURCE:
            if not is_explicit_request:
                return False
            # With explicit request and consent, it's eligible
            if consent_state == ConsentState.GRANTED:
                return True
            return False

        # Check base eligibility
        if not self._is_evidence_eligible(source_class):
            return False

        # Check consent state
        if self._is_consent_required(source_class):
            if consent_state != ConsentState.GRANTED:
                return False

        return True


_default_policy: Optional[SourcePolicy] = None
_policy_lock = threading.Lock()


def get_source_policy() -> SourcePolicy:
    """Get or create default SourcePolicy."""
    global _default_policy
    if _default_policy is None:
        with _policy_lock:
            if _default_policy is None:
                _default_policy = SourcePolicy()
    return _default_policy


def classify_source(envelope: HermesRuntimeEnvelope) -> SourceClassification:
    """Classify source from envelope using default policy."""
    return get_source_policy().classify(envelope)


def check_evidence_eligibility(
    source_class: SourceClass,
    consent_state: ConsentState,
    is_explicit_request: bool = False,
) -> bool:
    """Check evidence eligibility using default policy."""
    return get_source_policy().is_evidence_eligible(
        source_class=source_class,
        consent_state=consent_state,
        is_explicit_request=is_explicit_request,
    )
