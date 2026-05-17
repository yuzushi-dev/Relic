"""Tests for observation→ContinuityMarker promotion in facet_updater.

Contract:
- _promote_observation_to_marker skips when signal_strength < MARKER_PROMOTION_THRESHOLD
- _promote_observation_to_marker skips when observation_summary is empty
- _promote_observation_to_marker calls GumiContinuityStore.remember_marker when signal strong
- remember_marker called with correct subject_id, gumi_instance_id, hermes_profile_id
- subject_words derived from observation_summary.split()
- source_type == "subject_confirmed" (required for recent_markers() + prefetch() visibility)
- dedup: skips remember_marker when existing marker has same text
- fail-open: GumiContinuityStore exception does not propagate
- ttl_seconds == 1_209_600 (2 weeks)
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from relic.checkin.facet_updater import (
    MARKER_PROMOTION_THRESHOLD,
    ExtractionResult,
    _promote_observation_to_marker,
)


def _make_extraction(signal_strength: float, observation_summary: str = "osservazione") -> ExtractionResult:
    return ExtractionResult(
        facet_id="cognitive.decision_speed",
        exchange_id=1,
        informative=True,
        signal_position=0.7,
        signal_strength=signal_strength,
        observation_summary=observation_summary,
        confidence_delta=0.10,
    )


def _mock_store(existing_markers=None):
    """Return a configured mock GumiContinuityStore."""
    mock = MagicMock()
    mock.get_recent_markers.return_value = existing_markers or []
    return mock


class TestPromoteObservationToMarker:
    def test_below_threshold_no_call(self):
        extraction = _make_extraction(signal_strength=MARKER_PROMOTION_THRESHOLD - 0.01)
        with patch("relic.gumi_continuity.store.GumiContinuityStore") as mock_cls:
            _promote_observation_to_marker(extraction, "subj1")
        mock_cls.assert_not_called()

    def test_empty_summary_no_call(self):
        extraction = _make_extraction(signal_strength=0.9, observation_summary="")
        with patch("relic.gumi_continuity.store.GumiContinuityStore") as mock_cls:
            _promote_observation_to_marker(extraction, "subj1")
        mock_cls.assert_not_called()

    def test_at_threshold_calls_remember(self):
        extraction = _make_extraction(signal_strength=MARKER_PROMOTION_THRESHOLD)
        with patch("relic.gumi_continuity.store.GumiContinuityStore") as mock_cls:
            mock_cls.return_value = _mock_store()
            _promote_observation_to_marker(extraction, "subj1")
        mock_cls.return_value.remember_marker.assert_called_once()

    def test_above_threshold_calls_remember(self):
        extraction = _make_extraction(signal_strength=0.9)
        with patch("relic.gumi_continuity.store.GumiContinuityStore") as mock_cls:
            mock_cls.return_value = _mock_store()
            _promote_observation_to_marker(extraction, "subj1")
        mock_cls.return_value.remember_marker.assert_called_once()

    def test_passes_subject_id(self):
        extraction = _make_extraction(signal_strength=0.8, observation_summary="ama leggere")
        with patch("relic.gumi_continuity.store.GumiContinuityStore") as mock_cls:
            mock_cls.return_value = _mock_store()
            _promote_observation_to_marker(extraction, "my_subject")
        call_kwargs = mock_cls.return_value.remember_marker.call_args.kwargs
        assert call_kwargs["subject_id"] == "my_subject"

    def test_passes_gumi_and_hermes_ids(self):
        extraction = _make_extraction(signal_strength=0.8, observation_summary="ama leggere")
        with patch("relic.gumi_continuity.store.GumiContinuityStore") as mock_cls:
            mock_cls.return_value = _mock_store()
            _promote_observation_to_marker(
                extraction, "subj", gumi_instance_id="gumi-01", hermes_profile_id="hp-01"
            )
        call_kwargs = mock_cls.return_value.remember_marker.call_args.kwargs
        assert call_kwargs["gumi_instance_id"] == "gumi-01"
        assert call_kwargs["hermes_profile_id"] == "hp-01"

    def test_subject_words_from_summary(self):
        extraction = _make_extraction(
            signal_strength=0.8, observation_summary="preferisce messaggi brevi"
        )
        with patch("relic.gumi_continuity.store.GumiContinuityStore") as mock_cls:
            mock_cls.return_value = _mock_store()
            _promote_observation_to_marker(extraction, "subj")
        call_kwargs = mock_cls.return_value.remember_marker.call_args.kwargs
        assert call_kwargs["subject_words"] == ["preferisce", "messaggi", "brevi"]

    def test_source_type_is_subject_confirmed(self):
        """subject_confirmed required so recent_markers() + prefetch() can surface it."""
        extraction = _make_extraction(signal_strength=0.8)
        with patch("relic.gumi_continuity.store.GumiContinuityStore") as mock_cls:
            mock_cls.return_value = _mock_store()
            _promote_observation_to_marker(extraction, "subj")
        call_kwargs = mock_cls.return_value.remember_marker.call_args.kwargs
        assert call_kwargs["source_type"] == "subject_confirmed"

    def test_ttl_is_two_weeks(self):
        extraction = _make_extraction(signal_strength=0.8)
        with patch("relic.gumi_continuity.store.GumiContinuityStore") as mock_cls:
            mock_cls.return_value = _mock_store()
            _promote_observation_to_marker(extraction, "subj")
        call_kwargs = mock_cls.return_value.remember_marker.call_args.kwargs
        assert call_kwargs["ttl_seconds"] == 1_209_600

    def test_fail_open_on_store_exception(self):
        extraction = _make_extraction(signal_strength=0.8)
        with patch("relic.gumi_continuity.store.GumiContinuityStore") as mock_cls:
            store = _mock_store()
            store.remember_marker.side_effect = RuntimeError("db unavailable")
            mock_cls.return_value = store
            _promote_observation_to_marker(extraction, "subj")  # must not raise

    def test_fail_open_on_get_recent_markers_exception(self):
        extraction = _make_extraction(signal_strength=0.8)
        with patch("relic.gumi_continuity.store.GumiContinuityStore") as mock_cls:
            store = _mock_store()
            store.get_recent_markers.side_effect = RuntimeError("db error")
            mock_cls.return_value = store
            _promote_observation_to_marker(extraction, "subj")  # must not raise


class TestDedup:
    def test_skip_when_exact_duplicate_exists(self):
        """If existing marker has same text, remember_marker not called."""
        extraction = _make_extraction(
            signal_strength=0.8, observation_summary="preferisce messaggi brevi"
        )
        existing = [{"subject_words": ["preferisce", "messaggi", "brevi"]}]
        with patch("relic.gumi_continuity.store.GumiContinuityStore") as mock_cls:
            mock_cls.return_value = _mock_store(existing_markers=existing)
            _promote_observation_to_marker(extraction, "subj")
        mock_cls.return_value.remember_marker.assert_not_called()

    def test_call_when_no_matching_marker(self):
        """Different text → remember_marker IS called."""
        extraction = _make_extraction(
            signal_strength=0.8, observation_summary="ama leggere di notte"
        )
        existing = [{"subject_words": ["preferisce", "messaggi", "brevi"]}]
        with patch("relic.gumi_continuity.store.GumiContinuityStore") as mock_cls:
            mock_cls.return_value = _mock_store(existing_markers=existing)
            _promote_observation_to_marker(extraction, "subj")
        mock_cls.return_value.remember_marker.assert_called_once()

    def test_skip_handles_words_key_alias(self):
        """Dedup also checks 'words' key (alias used by some marker serializations)."""
        extraction = _make_extraction(
            signal_strength=0.8, observation_summary="tende a procrastinare"
        )
        existing = [{"words": ["tende", "a", "procrastinare"]}]
        with patch("relic.gumi_continuity.store.GumiContinuityStore") as mock_cls:
            mock_cls.return_value = _mock_store(existing_markers=existing)
            _promote_observation_to_marker(extraction, "subj")
        mock_cls.return_value.remember_marker.assert_not_called()

    def test_no_existing_markers_calls_remember(self):
        """Empty marker list → no dedup → remember_marker called."""
        extraction = _make_extraction(signal_strength=0.8, observation_summary="osservazione nuova")
        with patch("relic.gumi_continuity.store.GumiContinuityStore") as mock_cls:
            mock_cls.return_value = _mock_store(existing_markers=[])
            _promote_observation_to_marker(extraction, "subj")
        mock_cls.return_value.remember_marker.assert_called_once()


class TestFallbackIds:
    """When gumi_instance_id/hermes_profile_id are empty, subject_id used as sentinel.

    ContinuityService.remember() requires all three IDs non-empty or raises
    BLOCKED_MARKER_WITHOUT_SUBJECT_SCOPE. CLI runs without --gumi-instance-id /
    --hermes-profile-id so empty strings must be replaced with subject_id.
    """

    def test_empty_gumi_id_uses_subject_id(self):
        extraction = _make_extraction(signal_strength=0.8, observation_summary="ama leggere")
        with patch("relic.gumi_continuity.store.GumiContinuityStore") as mock_cls:
            mock_cls.return_value = _mock_store()
            _promote_observation_to_marker(
                extraction, "my_subject", gumi_instance_id="", hermes_profile_id="hp-01"
            )
        call_kwargs = mock_cls.return_value.remember_marker.call_args.kwargs
        assert call_kwargs["gumi_instance_id"] == "my_subject"
        assert call_kwargs["hermes_profile_id"] == "hp-01"

    def test_empty_hermes_id_uses_subject_id(self):
        extraction = _make_extraction(signal_strength=0.8, observation_summary="ama leggere")
        with patch("relic.gumi_continuity.store.GumiContinuityStore") as mock_cls:
            mock_cls.return_value = _mock_store()
            _promote_observation_to_marker(
                extraction, "my_subject", gumi_instance_id="gumi-01", hermes_profile_id=""
            )
        call_kwargs = mock_cls.return_value.remember_marker.call_args.kwargs
        assert call_kwargs["gumi_instance_id"] == "gumi-01"
        assert call_kwargs["hermes_profile_id"] == "my_subject"

    def test_both_empty_both_use_subject_id(self):
        """CLI default: no --gumi-instance-id / --hermes-profile-id → both fallback."""
        extraction = _make_extraction(signal_strength=0.8, observation_summary="usa il telefono la sera")
        with patch("relic.gumi_continuity.store.GumiContinuityStore") as mock_cls:
            mock_cls.return_value = _mock_store()
            _promote_observation_to_marker(
                extraction, "cli_subject", gumi_instance_id="", hermes_profile_id=""
            )
        call_kwargs = mock_cls.return_value.remember_marker.call_args.kwargs
        assert call_kwargs["gumi_instance_id"] == "cli_subject"
        assert call_kwargs["hermes_profile_id"] == "cli_subject"

    def test_provided_ids_not_overridden(self):
        """Non-empty IDs passed explicitly must NOT be replaced."""
        extraction = _make_extraction(signal_strength=0.8, observation_summary="legge molto")
        with patch("relic.gumi_continuity.store.GumiContinuityStore") as mock_cls:
            mock_cls.return_value = _mock_store()
            _promote_observation_to_marker(
                extraction, "subj", gumi_instance_id="gumi-99", hermes_profile_id="hp-99"
            )
        call_kwargs = mock_cls.return_value.remember_marker.call_args.kwargs
        assert call_kwargs["gumi_instance_id"] == "gumi-99"
        assert call_kwargs["hermes_profile_id"] == "hp-99"
