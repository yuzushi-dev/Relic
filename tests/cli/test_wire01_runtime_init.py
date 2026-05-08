"""Tests for WIRE01: Wire runtime feature initialization into relic init."""

from __future__ import annotations

import pytest
from unittest.mock import patch


class TestRelicInitInitializesRuntimeConfig:
    """test_relic_init_initializes_runtime_config"""

    def test_relic_init_initializes_runtime_config(self):
        """Verify init_runtime_config sets initialized=True."""
        from relic.hermes_runtime import init_runtime_config, get_runtime_config

        config = init_runtime_config()
        assert config.get("initialized") is True

        retrieved = get_runtime_config()
        assert retrieved.get("initialized") is True


class TestRelicInitDetectsHermesFeatures:
    """test_relic_init_detects_hermes_features"""

    def test_relic_init_detects_hermes_features(self):
        """Verify check_hermes_feature_support returns a dict with expected keys."""
        from relic.hermes_runtime import check_hermes_feature_support

        features = check_hermes_feature_support()

        assert isinstance(features, dict)
        assert "no_agent_cron" in features
        assert "transform_llm_output" in features
        assert "session_key_support" in features
        assert "allowlist_support" in features

    def test_hermes_version_checked_when_available(self):
        """Verify hermes version is checked."""
        from relic.hermes_runtime import check_hermes_feature_support

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "hermes 1.2.3"
            mock_run.return_value.stderr = ""

            features = check_hermes_feature_support()

            assert features.get("session_key_support") is True


class TestRelicInitDoesNotEnableDelivery:
    """test_relic_init_does_not_enable_delivery"""

    def test_init_does_not_enable_delivery(self):
        """Verify init does not enable delivery - storage is in-memory only."""
        from relic.hermes_runtime import (
            init_runtime_config,
            get_runtime_config,
            RuntimeDecision,
            DeliveryGate,
            ResumeReconciliation,
        )

        config = init_runtime_config()
        assert config.get("initialized") is True

        # Delivery is NOT enabled - storage is in-memory, no database
        runtime = get_runtime_config()
        assert "postgresql" not in str(runtime).lower()

        # RuntimeDecision exists as enum
        assert RuntimeDecision.NO_REPLY is not None

        # DeliveryGate exists
        gate = DeliveryGate(
            subject_id="test-subject",
            gumi_instance_id="test-gumi",
            hermes_profile_id="test-profile",
        )
        assert gate is not None

        # ResumeReconciliation exists
        from relic.hermes_runtime import SessionResumeState
        state = SessionResumeState(
            subject_id="test-subject",
            gumi_instance_id="test-gumi",
            hermes_profile_id="test-profile",
            session_key_hash="abc123",
        )
        recon = ResumeReconciliation(state)
        assert recon is not None
