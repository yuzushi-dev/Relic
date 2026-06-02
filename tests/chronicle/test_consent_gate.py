"""Tests for consent gate, T013.

Covers all scenarios from §8.2 of the agentic development plan:
1. consent_basis = None → allowed (system event)
2. subject_id = None → allowed (global event)
3. consent_basis in {SAFETY, PRIVACY, INCIDENT} → always allowed
4. ConsentManager.check_consent returns True → allowed
5. ConsentManager.check_consent returns False → denied
6. ConsentManager unavailable (test env) → allowed with warning
7. check_consent raises exception → allowed with warning
8. Unknown consent type → denied

Module: tests.chronicle.test_consent_gate
Reference: docs/chronicle/agentic-development-plan.md §8.2, T013
"""
from __future__ import annotations

import warnings
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest


class TestIsCaptureAllowed:
    """Test suite for is_capture_allowed()."""

    # -------------------------------------------------------------------------
    # Rule 1: consent_basis = None → allowed (system event)
    # -------------------------------------------------------------------------

    def test_none_consent_basis_allowed(self) -> None:
        """System events with no consent_basis are always allowed."""
        from relic.chronicle.consent_gate import is_capture_allowed

        allowed, reason = is_capture_allowed(
            consent_basis=None,
            subject_id="user_123",
            session_id=uuid4(),
        )
        assert allowed is True
        assert reason == "system_event"

    def test_none_consent_basis_no_subject(self) -> None:
        """None consent_basis with no subject returns system_event (preferred)."""
        from relic.chronicle.consent_gate import is_capture_allowed

        allowed, reason = is_capture_allowed(
            consent_basis=None,
            subject_id=None,
        )
        assert allowed is True
        assert reason == "system_event"

    # -------------------------------------------------------------------------
    # Rule 2: subject_id = None → allowed (global event)
    # -------------------------------------------------------------------------

    def test_no_subject_allowed(self) -> None:
        """Global events (no subject_id) are always allowed."""
        from relic.chronicle.consent_gate import is_capture_allowed

        allowed, reason = is_capture_allowed(
            consent_basis="MEMORY_STORAGE",
            subject_id=None,
        )
        assert allowed is True
        assert reason == "global_event"

    # -------------------------------------------------------------------------
    # Rule 3: Legitimate interest bases → always allowed
    # -------------------------------------------------------------------------

    @pytest.mark.parametrize("basis", ["SAFETY", "safety", "Safety", "PRIVACY", "privacy", "INCIDENT", "incident"])
    def test_legitimate_interest_allowed(self, basis: str) -> None:
        """SAFETY, PRIVACY, INCIDENT are allowed regardless of consent state."""
        from relic.chronicle.consent_gate import is_capture_allowed

        allowed, reason = is_capture_allowed(
            consent_basis=basis,
            subject_id="user_123",
            session_id=uuid4(),
        )
        assert allowed is True
        assert basis.lower() in reason

    # -------------------------------------------------------------------------
    # Rule 4: Explicit consent check via ConsentManager
    # -------------------------------------------------------------------------

    def test_consent_granted_allowed(self) -> None:
        """When ConsentManager.check_consent returns True, capture is allowed."""
        from relic.chronicle.consent_gate import is_capture_allowed

        session_id = uuid4()
        mock_manager = MagicMock()
        mock_manager.check_consent.return_value = True

        with patch("relic.chronicle.consent_gate._get_consent_manager", return_value=mock_manager):
            allowed, reason = is_capture_allowed(
                consent_basis="memory_storage",
                subject_id="user_123",
                session_id=session_id,
            )

        assert allowed is True
        assert "consent_granted" in reason

    def test_consent_denied_returns_false(self) -> None:
        """When ConsentManager.check_consent returns False, capture is denied."""
        from relic.chronicle.consent_gate import is_capture_allowed

        session_id = uuid4()
        mock_manager = MagicMock()
        mock_manager.check_consent.return_value = False

        with patch("relic.chronicle.consent_gate._get_consent_manager", return_value=mock_manager):
            allowed, reason = is_capture_allowed(
                consent_basis="memory_storage",
                subject_id="user_123",
                session_id=session_id,
            )

        assert allowed is False
        assert "consent_denied" in reason

    def test_unknown_consent_type_denied(self) -> None:
        """Unknown consent types are denied."""
        from relic.chronicle.consent_gate import is_capture_allowed

        session_id = uuid4()
        mock_manager = MagicMock()
        mock_manager.check_consent.return_value = False

        with patch("relic.chronicle.consent_gate._get_consent_manager", return_value=mock_manager):
            allowed, reason = is_capture_allowed(
                consent_basis="totally_invalid_type",
                subject_id="user_123",
                session_id=session_id,
            )

        assert allowed is False
        assert "unknown_consent_type" in reason

    # -------------------------------------------------------------------------
    # Rule 5: ConsentManager unavailable (test env) → allowed with warning
    # -------------------------------------------------------------------------

    def test_consent_manager_unavailable_allowed_with_warning(self) -> None:
        """When ConsentManager is None, capture is allowed with RuntimeWarning."""
        from relic.chronicle.consent_gate import is_capture_allowed

        with patch("relic.chronicle.consent_gate.ConsentManager", None):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                allowed, reason = is_capture_allowed(
                    consent_basis="memory_storage",
                    subject_id="user_123",
                    session_id=uuid4(),
                )

        assert allowed is True
        assert reason.startswith("consent_manager_unavailable")
        assert len(w) == 1
        assert issubclass(w[0].category, RuntimeWarning)

    # -------------------------------------------------------------------------
    # Rule 6: check_consent raises exception → allowed with warning
    # -------------------------------------------------------------------------

    def test_check_consent_raises_allowed_with_warning(self) -> None:
        """When check_consent raises, capture is allowed with logged warning."""
        from relic.chronicle.consent_gate import is_capture_allowed

        session_id = uuid4()
        mock_manager = MagicMock()
        mock_manager.check_consent.side_effect = RuntimeError("Database connection failed")

        with patch("relic.chronicle.consent_gate._get_consent_manager", return_value=mock_manager):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                allowed, reason = is_capture_allowed(
                    consent_basis="memory_storage",
                    subject_id="user_123",
                    session_id=session_id,
                )

        assert allowed is True
        assert "consent_check_error" in reason
        assert len(w) == 1
        assert issubclass(w[0].category, RuntimeWarning)

    # -------------------------------------------------------------------------
    # Additional edge cases
    # -------------------------------------------------------------------------

    def test_consent_type_enum_passed_directly(self) -> None:
        """ConsentType enum can be passed directly (not just strings)."""
        from relic.chronicle.consent_gate import is_capture_allowed

        from relic.control.consent import ConsentType

        session_id = uuid4()
        mock_manager = MagicMock()
        mock_manager.check_consent.return_value = True

        with patch("relic.chronicle.consent_gate._get_consent_manager", return_value=mock_manager):
            allowed, reason = is_capture_allowed(
                consent_basis=ConsentType.MEMORY_STORAGE,
                subject_id="user_123",
                session_id=session_id,
            )

        assert allowed is True
        assert "consent_granted" in reason

    def test_session_id_none_with_consent_basis(self) -> None:
        """session_id=None with explicit consent_basis goes through consent check."""
        from relic.chronicle.consent_gate import is_capture_allowed

        mock_manager = MagicMock()
        mock_manager.check_consent.return_value = True

        with patch("relic.chronicle.consent_gate._get_consent_manager", return_value=mock_manager):
            allowed, reason = is_capture_allowed(
                consent_basis="memory_storage",
                subject_id="user_123",
                session_id=None,
            )

        assert allowed is True
        # Verify check_consent was called with None session_id
        mock_manager.check_consent.assert_called_once()
        call_args = mock_manager.check_consent.call_args
        assert call_args[0][1] is None  # second positional arg is session_id

    def test_all_consent_types_enforced(self) -> None:
        """All ConsentType enum values should be checked via ConsentManager."""
        from relic.chronicle.consent_gate import is_capture_allowed
        from relic.control.consent import ConsentType

        session_id = uuid4()
        mock_manager = MagicMock()
        mock_manager.check_consent.return_value = True

        with patch("relic.chronicle.consent_gate._get_consent_manager", return_value=mock_manager):
            for consent_type in ConsentType:
                mock_manager.reset_mock()
                allowed, reason = is_capture_allowed(
                    consent_basis=consent_type,
                    subject_id="user_123",
                    session_id=session_id,
                )
                assert allowed is True, f"Failed for {consent_type}"
                mock_manager.check_consent.assert_called_once()
