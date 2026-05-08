"""Tests for pause/resume control functionality.

Acceptance criteria:
- pause does not disable CAC injection - MUST verify CAC injection is disabled when paused
"""

from __future__ import annotations

from uuid import uuid4

from relic.control.pause import PauseController, PauseState


class TestPauseController:
    """Tests for PauseController."""

    def test_pause_initial_state(self, temp_db):
        """Test that initially no pause is active."""
        controller = PauseController(db_path=str(temp_db))
        assert not controller.is_paused()

    def test_pause_session(self, temp_db):
        """Test pausing a session."""
        controller = PauseController(db_path=str(temp_db))
        session_id = uuid4()

        record = controller.pause(session_id=session_id, reason="user_initiated")

        assert record.state == PauseState.PAUSED
        assert record.session_id == session_id
        assert controller.is_paused(session_id)

    def test_resume_session(self, temp_db):
        """Test resuming a paused session."""
        controller = PauseController(db_path=str(temp_db))
        session_id = uuid4()

        controller.pause(session_id=session_id)
        assert controller.is_paused(session_id)

        record = controller.resume(session_id=session_id)
        assert record.state == PauseState.ACTIVE
        assert not controller.is_paused(session_id)

    def test_pause_resume_different_sessions(self, temp_db):
        """Test that pause state is session-specific."""
        controller = PauseController(db_path=str(temp_db))
        session_a = uuid4()
        session_b = uuid4()

        controller.pause(session_id=session_a)

        assert controller.is_paused(session_a)
        assert not controller.is_paused(session_b)

    def test_cac_injection_allowed_when_active(self, temp_db):
        """Test CAC injection is allowed when session is active."""
        controller = PauseController(db_path=str(temp_db))
        session_id = uuid4()

        assert controller.is_cac_injection_allowed(session_id)

    def test_cac_injection_disabled_when_paused(self, temp_db):
        """Test CAC injection is disabled when session is paused.

        This is the CRITICAL acceptance criterion:
        "pause does not disable CAC injection" is the BLOCK condition.
        """
        controller = PauseController(db_path=str(temp_db))
        session_id = uuid4()

        controller.pause(session_id=session_id)

        assert not controller.is_cac_injection_allowed(session_id)

    def test_cac_injection_re_enabled_after_resume(self, temp_db):
        """Test CAC injection is re-enabled after resume."""
        controller = PauseController(db_path=str(temp_db))
        session_id = uuid4()

        controller.pause(session_id=session_id)
        assert not controller.is_cac_injection_allowed(session_id)

        controller.resume(session_id=session_id)
        assert controller.is_cac_injection_allowed(session_id)

    def test_pause_history(self, temp_db):
        """Test getting pause history."""
        controller = PauseController(db_path=str(temp_db))
        session_id = uuid4()

        controller.pause(session_id=session_id, reason="first")
        controller.resume(session_id=session_id)
        controller.pause(session_id=session_id, reason="second")

        history = controller.get_pause_history(session_id, limit=10)

        assert len(history) >= 2
        assert any(r.state == PauseState.PAUSED and r.reason == "second" for r in history)
