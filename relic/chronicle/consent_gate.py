"""Consent gate module for Chronicle, T013.

Controls whether events can be written to the store based on consent rules.
Called BEFORE writing any event to ensure compliance with consent requirements.

Module: relic.chronicle.consent_gate
Version: consent-gate/v1
Reference: docs/chronicle/agentic-development-plan.md §8.2, T013
"""
from __future__ import annotations

import logging
import os
import warnings
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from relic.control.consent import ConsentType

logger = logging.getLogger(__name__)

# Legitimate interest bases: always allowed without explicit consent
_LEGITIMATE_INTEREST_BASES: set[str] = {"SAFETY", "PRIVACY", "INCIDENT"}


def _fail_open() -> bool:
    """Determine fail-open behaviour for ConsentManager errors/unavailability.

    Default: fail-closed (deny capture on error), safer GDPR posture.
    Override via env CHRONICLE_CONSENT_FAIL_OPEN=1 for dev/test bootstrap.
    """
    return os.environ.get("CHRONICLE_CONSENT_FAIL_OPEN", "0") == "1"

# ---------------------------------------------------------------------------
# ConsentManager import with graceful fallback
# ---------------------------------------------------------------------------

ConsentManager: type | None = None
_consent_manager_import_error: str | None = None

try:
    from relic.control.consent import ConsentManager as _CM
    ConsentManager = _CM
except Exception as exc:  # pragma: no cover
    _consent_manager_import_error = str(exc)
    ConsentManager = None


def _get_consent_manager() -> ConsentManager | None:
    """Get a ConsentManager instance, or None if unavailable (test env)."""
    if ConsentManager is None:
        return None
    return ConsentManager()


# ---------------------------------------------------------------------------
# is_capture_allowed
# ---------------------------------------------------------------------------

def is_capture_allowed(
    consent_basis: ConsentType | str | None,
    subject_id: str | None,
    session_id: UUID | None = None,
) -> tuple[bool, str]:
    """Returns (allowed, reason). Called BEFORE writing event to store.

    Rules:
    - consent_basis = None → allowed (system event, no PII)
    - subject_id = None → allowed (global event)
    - consent_basis in {SAFETY, PRIVACY, INCIDENT} → always allowed (legitimate interest)
    - else: ConsentManager.check_consent(consent_basis, session_id) must return True

    Args:
        consent_basis: Consent type identifier or None for system events.
        subject_id: Subject identifier or None for global events.
        session_id: Session UUID for consent lookup.

    Returns:
        tuple of (allowed: bool, reason: str)
    """
    # Rule 1: System event (no PII), always allowed
    if consent_basis is None:
        return True, "system_event"

    # Rule 2: Global event (no subject), always allowed
    if subject_id is None:
        return True, "global_event"

    # Rule 3: Legitimate interest bases: always allowed
    basis_str = str(consent_basis).upper()
    if basis_str in _LEGITIMATE_INTEREST_BASES:
        return True, f"legitimate_interest:{basis_str.lower()}"

    # Rule 4: Check explicit consent via ConsentManager
    if ConsentManager is None:
        # ConsentManager unavailable (test env or broken install).
        # Default: fail-closed (GDPR-safe). Override CHRONICLE_CONSENT_FAIL_OPEN=1 for bootstrap.
        if _fail_open():
            warnings.warn(
                f"ConsentManager unavailable ({_consent_manager_import_error}); "
                "CHRONICLE_CONSENT_FAIL_OPEN=1 → allowing capture.",
                RuntimeWarning,
            )
            return True, "consent_manager_unavailable_fail_open"
        return False, f"consent_manager_unavailable:{_consent_manager_import_error}"

    try:
        manager = _get_consent_manager()
        if manager is None:
            if _fail_open():
                return True, "consent_manager_instance_none_fail_open"
            return False, "consent_manager_instance_none"

        # Convert string basis to ConsentType if needed
        from relic.control.consent import ConsentType as CT

        if isinstance(consent_basis, str):
            try:
                consent_type = CT(consent_basis.lower())
            except ValueError:
                return False, f"unknown_consent_type:{consent_basis}"
        else:
            consent_type = consent_basis

        if manager.check_consent(consent_type, session_id):
            return True, f"consent_granted:{consent_type.value}"
        else:
            return False, f"consent_denied:{consent_type.value}"

    except Exception as exc:
        # Fail-closed by default: GDPR posture. Override with env var.
        logger.warning("Consent check raised %s: %s", type(exc).__name__, exc)
        if _fail_open():
            warnings.warn(
                f"ConsentManager.check_consent raised {type(exc).__name__}: {exc}; "
                "CHRONICLE_CONSENT_FAIL_OPEN=1 → allowing capture.",
                RuntimeWarning,
            )
            return True, f"consent_check_error_fail_open:{type(exc).__name__}"
        return False, f"consent_check_error:{type(exc).__name__}"
