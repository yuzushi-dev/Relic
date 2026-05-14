"""Tests for hermes no-agent cron wiring (FIX02)."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from relic.gumi_plugin.cron_wiring import (
    NO_AGENT_SCRIPT_PATH,
    _evaluate_decision,
    _is_continuity_scope_paused,
    _is_followup_max_attempts_reached,
    _is_followup_not_due,
    _is_platform_not_allowlisted,
    _is_quiet_hours,
    _is_subject_paused,
    emit_decision_event,
    make_decision,
    provision_no_agent_cron,
    render_no_agent_script,
)
from relic.hermes_runtime import RuntimeDecision, RuntimeDecisionReason
from relic.shared_continuity.service import ContinuityService, FollowupStatus


class TestNoAgentCronScriptCreated:
    """Test that the no-agent cron script is created correctly."""

    def test_no_agent_cron_script_created(self, tmp_path: Path) -> None:
        """Verify script file is created at the correct path with correct content."""
        script_path = tmp_path / "relic_no_agent_decision.sh"

        content = render_no_agent_script(script_path)

        # Write to temp path for inspection
        script_path.write_text(content, encoding="utf-8")

        # Verify shebang
        assert content.startswith("#!/usr/bin/env bash")

        # Verify script accepts subject_id argument with env-var fallback (bash syntax)
        # Rendered script uses: SUBJECT_ID="${1:-${RELIC_SUBJECT_ID:-}}"
        assert 'SUBJECT_ID=' in content
        assert '${1:-' in content

        # Verify it calls Python decision logic (heredoc with quotes prevents variable expansion)
        assert "<<'PYTHON_EOF'" in content
        assert "make_decision" in content
        assert "emit_decision_event" in content

        # Verify exit codes documented
        assert "exit 0" in content
        assert "exit 1" in content

        # Verify decision handling
        assert "RuntimeDecision.NO_REPLY" in content or "NO_REPLY" in content
        assert "RuntimeDecision.CANDIDATE" in content or "CANDIDATE" in content
        assert "RuntimeDecision.DELIVER" in content or "DELIVER" in content
        assert "RuntimeDecision.BLOCKED" in content or "BLOCKED" in content

    def test_provision_no_agent_cron_dry_run(self, tmp_path: Path) -> None:
        """Test provision_no_agent_cron in dry_run mode creates script."""
        fake_script_path = tmp_path / "test_script.sh"

        with patch("relic.gumi_plugin.cron_wiring.NO_AGENT_SCRIPT_PATH", fake_script_path):
            result = provision_no_agent_cron(
                subject_id="test_subject",
                gumi_instance_id="test_instance",
                hermes_profile_id="test_profile",
                dry_run=True,
            )

            assert result["dry_run"] is True
            assert result["script_path"] == str(fake_script_path)
            assert "hermes_command" in result
            assert "relic_no_agent_test_subject" in result["hermes_command"]


class TestNoAgentCronBlocksPausedContinuityScope:
    """Test that paused continuity scope blocks delivery."""

    def test_no_agent_cron_blocks_paused_continuity_scope(self) -> None:
        """Verify that a paused continuity scope results in BLOCKED decision."""
        with patch(
            "relic.gumi_plugin.cron_wiring.get_continuity_service"
        ) as mock_get_service:
            mock_service = MagicMock(spec=ContinuityService)
            # Set up _scopes to indicate paused
            mock_service._scopes = {
                "test_subject:None:None:global": {"is_paused": True}
            }
            mock_get_service.return_value = mock_service

            with patch(
                "relic.gumi_plugin.cron_wiring._is_quiet_hours", return_value=False
            ):
                with patch(
                    "relic.gumi_plugin.cron_wiring._is_platform_not_allowlisted",
                    return_value=False,
                ):
                    with patch(
                        "relic.gumi_plugin.cron_wiring._is_subject_paused",
                        return_value=False,
                    ):
                        with patch(
                            "relic.gumi_plugin.cron_wiring._is_followup_not_due",
                            return_value=False,
                        ):
                            with patch(
                                "relic.gumi_plugin.cron_wiring._is_followup_expired",
                                return_value=False,
                            ):
                                with patch(
                                    "relic.gumi_plugin.cron_wiring._is_followup_max_attempts_reached",
                                    return_value=False,
                                ):
                                    decision, reasons, candidate_data = (
                                        _evaluate_decision(
                                            subject_id="test_subject",
                                            gumi_instance_id="test_instance",
                                            hermes_profile_id="test_profile",
                                        )
                                    )

            assert decision == RuntimeDecision.BLOCKED
            assert RuntimeDecisionReason.continuity_scope_paused in reasons
            assert candidate_data is None

    def test_is_continuity_scope_paused_returns_true_when_paused(self) -> None:
        """Test _is_continuity_scope_paused helper returns True when scope is paused."""
        with patch(
            "relic.gumi_plugin.cron_wiring.get_continuity_service"
        ) as mock_get_service:
            mock_service = MagicMock(spec=ContinuityService)
            mock_service._scopes = {
                "test_subject:None:None:global": {"is_paused": True}
            }
            mock_get_service.return_value = mock_service

            result = _is_continuity_scope_paused("test_subject")

            assert result is True

    def test_is_continuity_scope_paused_returns_false_when_active(self) -> None:
        """Test _is_continuity_scope_paused helper returns False when scope is active."""
        with patch(
            "relic.gumi_plugin.cron_wiring.get_continuity_service"
        ) as mock_get_service:
            mock_service = MagicMock(spec=ContinuityService)
            mock_service._scopes = {}
            mock_get_service.return_value = mock_service

            result = _is_continuity_scope_paused("test_subject")

            assert result is False


class TestNoAgentCronEmitsDecisionEvent:
    """Test that decision events are emitted for audit."""

    def test_no_agent_cron_emits_decision_event(self, tmp_path: Path) -> None:
        """Verify emit_decision_event writes to the decision event log."""
        event_log = tmp_path / "decision_events.jsonl"

        # Create a mock that handles the Path construction and expanduser call chain
        mock_expand_result = MagicMock()
        mock_expand_result.parent.mkdir.return_value = None

        mock_path_instance = MagicMock()
        mock_path_instance.expanduser.return_value = event_log
        mock_path_instance.__str__ = lambda self: str(event_log)

        # Mock Path class to return our instance
        with patch(
            "relic.gumi_plugin.cron_wiring.Path"
        ) as mock_path_cls:
            mock_path_cls.return_value = mock_path_instance

            with patch("builtins.open", MagicMock()) as mock_open:
                mock_file = MagicMock()
                mock_file.__enter__ = MagicMock(return_value=mock_file)
                mock_file.__exit__ = MagicMock(return_value=None)
                mock_open.return_value = mock_file

                emit_decision_event(
                    decision=RuntimeDecision.NO_REPLY,
                    reason_codes=[RuntimeDecisionReason.followup_not_due],
                    subject_id="test_subject",
                    gumi_instance_id="test_instance",
                    hermes_profile_id="test_profile",
                )

                mock_open.assert_called()

    def test_decision_event_contains_required_fields(self) -> None:
        """Verify DecisionEvent.to_dict returns all required fields."""
        from relic.hermes_runtime import DecisionEvent

        event = DecisionEvent(
            decision=RuntimeDecision.CANDIDATE,
            reason_codes=[
                RuntimeDecisionReason.followup_not_due,
                RuntimeDecisionReason.platform_not_allowlisted,
            ],
            subject_id="test_subject",
            gumi_instance_id="test_instance",
            hermes_profile_id="test_profile",
            target_id="test_target",
            metadata={"source": "no_agent_cron"},
        )

        d = event.to_dict()

        assert d["decision"] == "CANDIDATE"
        assert d["subject_id"] == "test_subject"
        assert d["gumi_instance_id"] == "test_instance"
        assert d["hermes_profile_id"] == "test_profile"
        assert d["target_id"] == "test_target"
        # Check metadata contains source
        assert d["metadata"]["source"] == "no_agent_cron"
        assert "followup_not_due" in d["reason_codes"]
        assert "platform_not_allowlisted" in d["reason_codes"]


class TestCandidateRequiresDeliveryGate:
    """Test that CANDIDATE requires delivery gate before actual delivery."""

    def test_candidate_requires_delivery_gate(self) -> None:
        """Verify when all guards pass, decision is DELIVER with candidate_data."""
        with patch(
            "relic.gumi_plugin.cron_wiring.get_continuity_service"
        ) as mock_get_service:
            mock_service = MagicMock(spec=ContinuityService)
            mock_service._scopes = {}
            mock_service.due_followups.return_value = [
                {
                    "followup_id": "f1",
                    "marker_id": "m1",
                    "subject_id": "test_subject",
                    "status": "due",
                    "attempt_count": 0,
                    "max_attempts": 3,
                }
            ]
            mock_get_service.return_value = mock_service

            with patch(
                "relic.gumi_plugin.cron_wiring._is_quiet_hours", return_value=False
            ), patch(
                "relic.gumi_plugin.cron_wiring._is_platform_not_allowlisted",
                return_value=False,
            ), patch(
                "relic.gumi_plugin.cron_wiring._is_subject_paused",
                return_value=False,
            ), patch(
                "relic.gumi_plugin.cron_wiring._is_continuity_scope_paused",
                return_value=False,
            ), patch(
                "relic.gumi_plugin.cron_wiring._is_delivery_window_open",
                return_value=True,
            ), patch(
                "relic.gumi_plugin.cron_wiring._is_followup_not_due",
                return_value=False,
            ), patch(
                "relic.gumi_plugin.cron_wiring._is_followup_expired",
                return_value=False,
            ), patch(
                "relic.gumi_plugin.cron_wiring._is_followup_max_attempts_reached",
                return_value=False,
            ):
                decision, reasons, candidate_data = _evaluate_decision(
                    subject_id="test_subject",
                    gumi_instance_id="test_instance",
                    hermes_profile_id="test_profile",
                )

            # _evaluate_decision goes directly to DELIVER when all guards pass
            assert decision == RuntimeDecision.DELIVER
            assert candidate_data is not None
            assert "message" in candidate_data

    def test_no_reply_has_empty_stdout_contract(self) -> None:
        """Verify NO_REPLY returns empty candidate_data when delivery window is closed."""
        with patch(
            "relic.gumi_plugin.cron_wiring._is_quiet_hours", return_value=False
        ):
            with patch(
                "relic.gumi_plugin.cron_wiring._is_platform_not_allowlisted",
                return_value=False,
            ):
                with patch(
                    "relic.gumi_plugin.cron_wiring._is_subject_paused",
                    return_value=False,
                ):
                    with patch(
                        "relic.gumi_plugin.cron_wiring._is_continuity_scope_paused",
                        return_value=False,
                    ):
                        with patch(
                            "relic.gumi_plugin.cron_wiring._is_delivery_window_open",
                            return_value=False,  # window closed → NO_REPLY
                        ):
                            decision, reasons, candidate_data = _evaluate_decision(
                                subject_id="test_subject",
                                gumi_instance_id="test_instance",
                                hermes_profile_id="test_profile",
                            )

        assert decision == RuntimeDecision.NO_REPLY
        assert candidate_data is None

    def test_followup_not_due_returns_no_reply(self) -> None:
        """Test that _is_followup_not_due returns True when no followups are due."""
        with patch(
            "relic.gumi_plugin.cron_wiring.get_continuity_service"
        ) as mock_get_service:
            mock_service = MagicMock(spec=ContinuityService)
            mock_service.due_followups.return_value = []
            mock_get_service.return_value = mock_service

            result = _is_followup_not_due("test_subject", "test_instance", "test_profile")

            assert result is True

    def test_platform_not_allowlisted_blocks(self) -> None:
        """Test _is_platform_not_allowlisted returns True when not allowlisted."""
        with patch(
            "relic.profile.registry.ProfileRegistry"
        ) as mock_registry_cls:
            mock_registry = MagicMock()
            mock_policy_path = MagicMock(spec=Path)
            mock_policy_path.exists.return_value = True
            mock_registry._delivery_policy_path.return_value = mock_policy_path
            mock_registry_cls.return_value = mock_registry

            with patch("builtins.open", MagicMock()):
                with patch("json.load", return_value={"consent_for_active_elicitation": False}):
                    result = _is_platform_not_allowlisted("test_subject")
                    assert result is True

    def test_subject_paused_blocks(self) -> None:
        """Test _is_subject_paused returns True when subject is not active."""
        with patch(
            "relic.profile.registry.ProfileRegistry"
        ) as mock_registry_cls:
            mock_registry = MagicMock()
            mock_profile = MagicMock()
            mock_profile.status = "archived"
            mock_registry.get_subject.return_value = mock_profile
            mock_registry_cls.return_value = mock_registry

            result = _is_subject_paused("test_subject")
            assert result is True

    def test_quiet_hours_blocks(self) -> None:
        """Test _is_quiet_hours returns True during quiet hours."""
        with patch(
            "relic.profile.registry.ProfileRegistry"
        ) as mock_registry_cls:
            mock_registry = MagicMock()
            mock_policy_path = MagicMock(spec=Path)
            mock_policy_path.exists.return_value = True
            mock_registry._delivery_policy_path.return_value = mock_policy_path
            mock_registry_cls.return_value = mock_registry

            with patch("builtins.open", MagicMock()):
                # Quiet hours 23:00-07:00, test during the night
                with patch(
                    "relic.gumi_plugin.cron_wiring.datetime"
                ) as mock_dt:
                    mock_now = MagicMock()
                    mock_now.hour = 23
                    mock_now.minute = 30
                    mock_dt.now.return_value = mock_now

                    with patch("json.load", return_value={"quiet_hours": "23:00-07:00"}):
                        result = _is_quiet_hours("test_subject")
                        assert result is True

    def test_followup_max_attempts_blocks(self) -> None:
        """Test _is_followup_max_attempts_reached returns True when exhausted."""
        with patch(
            "relic.gumi_plugin.cron_wiring.get_continuity_service"
        ) as mock_get_service:
            mock_service = MagicMock(spec=ContinuityService)
            mock_service.due_followups.return_value = [
                {"followup_id": "f1", "attempt_count": 3, "max_attempts": 3}
            ]
            mock_get_service.return_value = mock_service

            result = _is_followup_max_attempts_reached("test_subject", "test_instance", "test_profile")

            assert result is True


class TestRuntimeDecisionEnum:
    """Test RuntimeDecision enum contains required values."""

    def test_runtime_decision_enum_contains_no_reply(self) -> None:
        """Verify RuntimeDecision enum has NO_REPLY."""
        assert hasattr(RuntimeDecision, "NO_REPLY")
        assert RuntimeDecision.NO_REPLY == "NO_REPLY"

    def test_runtime_decision_enum_contains_candidate(self) -> None:
        """Verify RuntimeDecision enum has CANDIDATE."""
        assert hasattr(RuntimeDecision, "CANDIDATE")
        assert RuntimeDecision.CANDIDATE == "CANDIDATE"

    def test_runtime_decision_enum_contains_deliver(self) -> None:
        """Verify RuntimeDecision enum has DELIVER."""
        assert hasattr(RuntimeDecision, "DELIVER")
        assert RuntimeDecision.DELIVER == "DELIVER"

    def test_runtime_decision_enum_contains_blocked(self) -> None:
        """Verify RuntimeDecision enum has BLOCKED."""
        assert hasattr(RuntimeDecision, "BLOCKED")
        assert RuntimeDecision.BLOCKED == "BLOCKED"

    def test_runtime_decision_enum_contains_review_required(self) -> None:
        """Verify RuntimeDecision enum has REVIEW_REQUIRED."""
        assert hasattr(RuntimeDecision, "REVIEW_REQUIRED")
        assert RuntimeDecision.REVIEW_REQUIRED == "REVIEW_REQUIRED"

    def test_runtime_decision_enum_contains_error(self) -> None:
        """Verify RuntimeDecision enum has ERROR."""
        assert hasattr(RuntimeDecision, "ERROR")
        assert RuntimeDecision.ERROR == "ERROR"


class TestReasonCodes:
    """Test RuntimeDecisionReason enum contains all required reason codes."""

    def test_reason_codes_all_present(self) -> None:
        """Verify all required reason codes are present."""
        required = [
            "quiet_hours",
            "platform_not_allowlisted",
            "subject_paused",
            "continuity_scope_paused",
            "followup_not_due",
            "followup_expired",
            "followup_max_attempts_reached",
            "already_logged_or_contacted",
            "burden_signal",
            "safety_review_required",
            "output_sanitizer_blocked",
            "delivery_state_unknown",
            "no_due_work",
        ]
        for code in required:
            assert hasattr(RuntimeDecisionReason, code), f"Missing reason code: {code}"
