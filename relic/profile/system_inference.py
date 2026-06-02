"""PR08, system_inferred_fields update loop.

Reads only governed traces and redacted metadata, never raw prompt text.
Updates estimated_engagement_level, inferred_relational_style,
session_affect_summary, response_latency_pattern.
"""
from __future__ import annotations

from typing import Any

from relic.profile.inferred_fields import (
    DEFAULT_CONFIDENCE_CAP,
    InferredField,
    validate_inferred_field_value,
)

RAW_PROMPT_MARKERS = (
    "SECRET_RAW_PROMPT_SHOULD_NOT_APPEAR",
    "PRIVATE_HEALTH_DETAIL_SHOULD_NOT_APPEAR",
    "raw_final_prompt",
    "raw_session_text",
)


def _reject_raw_prompt(source: Any) -> None:
    """Raise ValueError if source contains raw prompt markers."""
    text = str(source) if not isinstance(source, str) else source
    for marker in RAW_PROMPT_MARKERS:
        if marker in text:
            raise ValueError(
                f"system_inference must not read raw prompt text (found marker: {marker!r})"
            )


def _safe_confidence(source_refs: list[str]) -> float:
    from relic.profile.inferred_fields import MULTI_EVIDENCE_CAP
    if len(source_refs) >= 2:
        return MULTI_EVIDENCE_CAP
    return DEFAULT_CONFIDENCE_CAP


class SystemInferenceUpdater:
    """Update system_inferred_fields from governed traces only.

    Acceptable inputs:
    - redacted exposure events (dict with event_type, redacted_summary, source_ref)
    - timing metadata (response_latency_ms, session_duration_s)
    - memory dynamics events (MemoryDynamicsEvent dicts)

    Forbidden inputs:
    - raw prompt text
    - raw session transcripts
    - clinical labels
    """

    def update_engagement_level(
        self,
        exposure_events: list[dict[str, Any]],
    ) -> InferredField:
        """Estimate engagement from exposure event count and types."""
        source_refs = []
        for ev in exposure_events:
            raw = ev.get("raw_text") or ev.get("raw_prompt") or ""
            _reject_raw_prompt(raw)
            ref = ev.get("source_ref") or ev.get("event_id", "")
            if ref:
                source_refs.append(ref)

        count = len(exposure_events)
        if count == 0:
            value = "unknown"
        elif count <= 2:
            value = "low"
        elif count <= 5:
            value = "moderate"
        else:
            value = "high"

        validate_inferred_field_value(value)
        return InferredField(
            field_name="estimated_engagement_level",
            value=value,
            confidence=_safe_confidence(source_refs),
            source_refs=source_refs,
        )

    def update_relational_style(
        self,
        dynamics_events: list[dict[str, Any]],
    ) -> InferredField:
        """Infer relational style from memory dynamics events."""
        source_refs = []
        reinforcement_count = 0
        decay_count = 0
        for ev in dynamics_events:
            _reject_raw_prompt(ev.get("raw_text", ""))
            ref = ev.get("event_id", "")
            if ref:
                source_refs.append(ref)
            etype = ev.get("event_type", "")
            if etype == "reinforcement":
                reinforcement_count += 1
            elif etype == "decay":
                decay_count += 1

        if reinforcement_count > decay_count:
            value = "engaged"
        elif decay_count > reinforcement_count:
            value = "distanced"
        else:
            value = "neutral"

        validate_inferred_field_value(value)
        return InferredField(
            field_name="inferred_relational_style",
            value=value,
            confidence=_safe_confidence(source_refs),
            source_refs=source_refs,
        )

    def update_session_affect_summary(
        self,
        redacted_exposure_events: list[dict[str, Any]],
    ) -> InferredField:
        """Build affect summary from redacted event summaries only."""
        source_refs = []
        summaries = []
        for ev in redacted_exposure_events:
            _reject_raw_prompt(ev.get("raw_text", ""))
            summary = ev.get("redacted_summary", "")
            if summary:
                summaries.append(summary)
            ref = ev.get("source_ref") or ev.get("event_id", "")
            if ref:
                source_refs.append(ref)

        value = "; ".join(summaries[:3]) if summaries else None
        if value:
            validate_inferred_field_value(value)
        return InferredField(
            field_name="session_affect_summary",
            value=value,
            confidence=_safe_confidence(source_refs),
            source_refs=source_refs,
        )

    def update_response_latency_pattern(
        self,
        latency_metadata: list[dict[str, Any]],
    ) -> InferredField:
        """Summarize response latency from timing metadata."""
        source_refs = []
        latencies = []
        for meta in latency_metadata:
            _reject_raw_prompt(meta.get("raw_text", ""))
            ms = meta.get("response_latency_ms")
            if isinstance(ms, (int, float)):
                latencies.append(ms)
            ref = meta.get("source_ref", "")
            if ref:
                source_refs.append(ref)

        if not latencies:
            value = None
        else:
            avg = sum(latencies) / len(latencies)
            if avg < 2000:
                value = "fast"
            elif avg < 10000:
                value = "moderate"
            else:
                value = "slow"

        if value:
            validate_inferred_field_value(value)
        return InferredField(
            field_name="response_latency_pattern",
            value=value,
            confidence=_safe_confidence(source_refs),
            source_refs=source_refs,
        )

    def run(
        self,
        *,
        exposure_events: list[dict[str, Any]] | None = None,
        dynamics_events: list[dict[str, Any]] | None = None,
        latency_metadata: list[dict[str, Any]] | None = None,
        subject_id: str,
    ) -> dict[str, InferredField]:
        """Run all inferred field updates for a subject. Returns field map."""
        result: dict[str, InferredField] = {}
        result["estimated_engagement_level"] = self.update_engagement_level(
            exposure_events or []
        )
        result["inferred_relational_style"] = self.update_relational_style(
            dynamics_events or []
        )
        result["session_affect_summary"] = self.update_session_affect_summary(
            exposure_events or []
        )
        result["response_latency_pattern"] = self.update_response_latency_pattern(
            latency_metadata or []
        )
        return result
