"""Tests for observation→ContinuityMarker promotion in facet_updater.

Contract:
- _promote_observation_to_marker skips when signal_strength < MARKER_PROMOTION_THRESHOLD
- _promote_observation_to_marker skips when observation_summary is empty
- _promote_observation_to_marker calls GumiContinuityStore.remember_marker when signal strong
- remember_marker called with correct subject_id, gumi_instance_id, hermes_profile_id
- subject_words derived from observation_summary.split()
- source_type == "checkin_observation"
- fail-open: GumiContinuityStore exception does not propagate
- process_pending_exchanges passes gumi_instance_id + hermes_profile_id to _promote
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


class TestPromoteObservationToMarker:
    def test_below_threshold_no_call(self):
        extraction = _make_extraction(signal_strength=MARKER_PROMOTION_THRESHOLD - 0.01)
        with patch("relic.gumi_continuity.store.GumiContinuityStore") as mock_cls:
            _promote_observation_to_marker(extraction, "subj1")
        mock_cls.assert_not_called()

    def test_at_threshold_calls_remember(self):
        extraction = _make_extraction(signal_strength=MARKER_PROMOTION_THRESHOLD)
        with patch("relic.gumi_continuity.store.GumiContinuityStore") as mock_cls:
            mock_store = MagicMock()
            mock_cls.return_value = mock_store
            _promote_observation_to_marker(extraction, "subj1")
        mock_store.remember_marker.assert_called_once()

    def test_above_threshold_calls_remember(self):
        extraction = _make_extraction(signal_strength=0.9)
        with patch("relic.gumi_continuity.store.GumiContinuityStore") as mock_cls:
            mock_store = MagicMock()
            mock_cls.return_value = mock_store
            _promote_observation_to_marker(extraction, "subj1")
        mock_store.remember_marker.assert_called_once()

    def test_empty_summary_no_call(self):
        extraction = _make_extraction(signal_strength=0.9, observation_summary="")
        with patch("relic.gumi_continuity.store.GumiContinuityStore") as mock_cls:
            _promote_observation_to_marker(extraction, "subj1")
        mock_cls.assert_not_called()

    def test_passes_subject_id(self):
        extraction = _make_extraction(signal_strength=0.8, observation_summary="ama leggere")
        with patch("relic.gumi_continuity.store.GumiContinuityStore") as mock_cls:
            mock_store = MagicMock()
            mock_cls.return_value = mock_store
            _promote_observation_to_marker(extraction, "my_subject")
        call_kwargs = mock_store.remember_marker.call_args.kwargs
        assert call_kwargs["subject_id"] == "my_subject"

    def test_passes_gumi_and_hermes_ids(self):
        extraction = _make_extraction(signal_strength=0.8, observation_summary="ama leggere")
        with patch("relic.gumi_continuity.store.GumiContinuityStore") as mock_cls:
            mock_store = MagicMock()
            mock_cls.return_value = mock_store
            _promote_observation_to_marker(
                extraction, "subj", gumi_instance_id="gumi-01", hermes_profile_id="hp-01"
            )
        call_kwargs = mock_store.remember_marker.call_args.kwargs
        assert call_kwargs["gumi_instance_id"] == "gumi-01"
        assert call_kwargs["hermes_profile_id"] == "hp-01"

    def test_subject_words_from_summary(self):
        extraction = _make_extraction(
            signal_strength=0.8, observation_summary="preferisce messaggi brevi"
        )
        with patch("relic.gumi_continuity.store.GumiContinuityStore") as mock_cls:
            mock_store = MagicMock()
            mock_cls.return_value = mock_store
            _promote_observation_to_marker(extraction, "subj")
        call_kwargs = mock_store.remember_marker.call_args.kwargs
        assert call_kwargs["subject_words"] == ["preferisce", "messaggi", "brevi"]

    def test_source_type_is_checkin_observation(self):
        extraction = _make_extraction(signal_strength=0.8)
        with patch("relic.gumi_continuity.store.GumiContinuityStore") as mock_cls:
            mock_store = MagicMock()
            mock_cls.return_value = mock_store
            _promote_observation_to_marker(extraction, "subj")
        call_kwargs = mock_store.remember_marker.call_args.kwargs
        assert call_kwargs["source_type"] == "checkin_observation"

    def test_fail_open_on_store_exception(self):
        extraction = _make_extraction(signal_strength=0.8)
        with patch("relic.gumi_continuity.store.GumiContinuityStore") as mock_cls:
            mock_store = MagicMock()
            mock_store.remember_marker.side_effect = RuntimeError("db unavailable")
            mock_cls.return_value = mock_store
            # Must not raise
            _promote_observation_to_marker(extraction, "subj")

    def test_ttl_is_two_weeks(self):
        extraction = _make_extraction(signal_strength=0.8)
        with patch("relic.gumi_continuity.store.GumiContinuityStore") as mock_cls:
            mock_store = MagicMock()
            mock_cls.return_value = mock_store
            _promote_observation_to_marker(extraction, "subj")
        call_kwargs = mock_store.remember_marker.call_args.kwargs
        assert call_kwargs["ttl_seconds"] == 1_209_600
