"""PR03/PR05, Hermes lifecycle hooks for Relic Shared Continuity.

pre_llm_call:
  Builds PromptContextPack from continuity markers (ContinuityAdmissionPolicy)
  and returns {"context": <redacted string>} for Hermes to inject into the
  user message.  Fail-closed: any exception → return None, no context injected.

transform_llm_output:
  Runs OutputCritic on the LLM response.  Blocks false lived experience,
  dependency claims, and clinical labels.  Returns None (pass-through) or
  a replacement string.

post_llm_call:
  Fire-and-forget observer, return value ignored by Hermes.
"""

from __future__ import annotations

import hashlib
import logging
from itertools import count

logger = logging.getLogger(__name__)

FORBIDDEN_OUTPUT_TERMS = [
    "bipolar", "mania", "hypomania", "depression",
    "episode", "symptom", "diagnosis", "relapse", "pathology",
    "I detected a pattern", "the system noticed", "Relic detected"
]

_SILENT = "[SILENT]"
_EVENT_REF_COUNTER = count()

try:
    from relic.safety.signal_aggregator import InMemorySafetySignalAggregator
    _SAFETY_AGGREGATOR = InMemorySafetySignalAggregator()
except Exception:  # pragma: no cover - hook bootstrap must remain best-effort
    _SAFETY_AGGREGATOR = None


def pre_llm_call(
    *,
    session_id: str = "",
    user_message: str = "",
    conversation_history: list | None = None,
    is_first_turn: bool = False,
    model: str = "",
    platform: str = "",
    sender_id: str = "",
    **kwargs,
) -> dict | None:
    """Build PromptContextPack and return {"context": str} for Hermes injection.

    Uses session_id as subject_id scope when no explicit subject mapping exists.
    Fail-closed: any exception returns None (no context injected).
    """
    try:
        from relic.gumi_continuity.admission import get_admission_policy
        from relic.context_pack.types import (
            PromptContextPack,
            TaskType,
            RoleplayLevel,
            ContinuityMode,
            ContinuityItem,
            BlockedItem,
        )
        from relic.context_pack.render import render_compact

        subject_id = sender_id or session_id
        if not subject_id:
            return None

        # Fetch recent markers from continuity service (fail-open: empty list on error)
        raw_markers: list[dict] = []
        try:
            from relic.shared_continuity.service import get_continuity_service
            svc = get_continuity_service()
            raw_markers = svc.recent_markers(subject_id=subject_id, limit=20) or []
            if raw_markers and hasattr(raw_markers[0], "__dict__"):
                # ContinuityMarker dataclass → dict
                raw_markers = [m.__dict__ for m in raw_markers]
        except Exception:
            raw_markers = []

        # Run ContinuityAdmissionPolicy
        policy = get_admission_policy()
        decisions = policy.evaluate_markers(raw_markers)

        admitted_markers = [
            raw_markers[i]
            for i, d in enumerate(decisions)
            if d.admitted and i < len(raw_markers)
        ]
        blocked_decisions = [d for d in decisions if not d.admitted]

        # Build minimal PromptContextPack
        continuity_items = [
            ContinuityItem(
                item_id=m.get("marker_id", f"m-{i}"),
                item_type="continuity_marker",
                summary=" ".join(m.get("subject_words") or m.get("gumi_agreed_words") or []),
                scope=[],
            )
            for i, m in enumerate(admitted_markers)
        ]

        blocked_items = [
            BlockedItem(
                item_id=d.marker_id,
                reason=d.reason or d.blocked_by or "admission_policy",
                scope=[],
            )
            for d in blocked_decisions
        ]

        pack = PromptContextPack(
            session_id=session_id,
            task_type=TaskType.RELATIONAL,
            roleplay_level=RoleplayLevel.LIGHT,
            continuity_mode=ContinuityMode.COMPACT if continuity_items else ContinuityMode.NONE,
            continuity_items=continuity_items,
            blocked_items=blocked_items,
        )

        if not continuity_items:
            return None

        injected = render_compact(pack)
        pack.injected_context_redacted = injected

        return {"context": injected}

    except Exception as exc:
        logger.warning("pre_llm_call hook failed (fail-closed): %s", type(exc).__name__)
        return None
    finally:
        # Safety signal scan: fire-and-forget, never blocks Hermes turn.
        # Runs in finally so it executes even when context injection returns early.
        if user_message:
            _run_safety_scan(
                subject_id=sender_id or session_id,
                user_message=user_message,
                session_id=session_id,
            )


def _run_safety_scan(subject_id: str, user_message: str, session_id: str) -> None:
    """Extract safety signals from user message and escalate if needed.

    Privacy: user_message is scanned but never stored or logged.
    Only signal_type + subject_id + timestamp are written to the audit log.
    """
    if not subject_id or not user_message:
        return
    try:
        from relic.patterns.signal_extractor import SafetySignalExtractor
        from relic.safety.escalation_notifier import notify_escalation
        from relic.safety.signal_audit import write_signal_audit

        extractor = SafetySignalExtractor()
        event_ref = _redacted_event_ref(user_message)
        result = extractor.extract(
            subject_id=subject_id,
            gumi_instance_id=subject_id,
            hermes_profile_id=f"gumi-{subject_id}",
            events=[{"text": user_message, "event_id": event_ref}],
        )

        evidence_refs = [event_ref]
        if result.crisis_bypassed and result.crisis_signal_type:
            notify_escalation(
                subject_id,
                result.crisis_signal_type,
                evidence_refs=evidence_refs,
                warning_tier="T4_crisis",
                confidence=0.85,
            )
            return

        # Notify on repeated non-crisis signals after aggregation. Hermes hooks
        # receive one turn at a time, so a single non-crisis mention stays queued.
        for signal in result.signals:
            if _SAFETY_AGGREGATOR is None:
                _write_signal_audit_safely(write_signal_audit, signal, disposition="queued")
                continue
            aggregated = _SAFETY_AGGREGATOR.record(signal)
            _write_signal_audit_safely(
                write_signal_audit,
                signal,
                disposition="notified" if aggregated.should_notify else "queued",
                extra={
                    "aggregated_event_count": aggregated.event_count,
                    "aggregated_confidence": aggregated.confidence,
                    "aggregated_warning_tier": aggregated.warning_tier,
                },
            )
            if aggregated.should_notify:
                notify_escalation(
                    subject_id,
                    signal.signal_family,
                    evidence_refs=aggregated.evidence_refs,
                    warning_tier=aggregated.warning_tier,
                    confidence=aggregated.confidence,
                )

    except Exception as exc:
        logger.warning("_run_safety_scan failed (ignored): %s", type(exc).__name__)


def _write_signal_audit_safely(write_signal_audit, signal, **kwargs) -> None:
    """Write signal audit without letting audit I/O block Hermes hooks."""
    try:
        write_signal_audit(signal, **kwargs)
    except Exception as exc:
        logger.warning("safety signal audit failed (ignored): %s", type(exc).__name__)


def _redacted_event_ref(user_message: str) -> str:
    """Build a per-turn evidence ref without retaining raw user text."""
    nonce = next(_EVENT_REF_COUNTER)
    digest = hashlib.sha256(f"{nonce}:{user_message}".encode("utf-8")).hexdigest()[:16]
    return f"turn-{digest}"


def post_llm_call(*args, **kwargs) -> None:
    """Fire-and-forget observer, return value ignored by Hermes."""
    return None


def transform_llm_output(output=None, *args, **kwargs) -> str | None:
    """Run OutputCritic then fallback term-list filter.

    Returns:
        None, pass-through (no change)
        str, replacement text (critic blocked or clinical term found)
    """
    if output is None:
        return None

    text = str(output)

    # PR05: OutputCritic (false experience, dependency, disclosure)
    try:
        from relic.gumi_plugin.critic import OutputCritic
        verdict = OutputCritic().review(text, consensual=True)
        if not verdict.allow:
            if verdict.reason == "false_physical_experience":
                return _SILENT
            # dependency/need claim: replace with neutral redirect
            return (
                "I'm here with you in this. "
                "What would feel most helpful right now?"
            )
    except Exception:
        pass

    # Fallback: clinical term filter
    lower = text.lower()
    hits = [term for term in FORBIDDEN_OUTPUT_TERMS if term.lower() in lower]
    if hits:
        return (
            "I will keep this in your words, without putting labels on it. "
            "If you want, we can just hold onto the thread and come back to it gently."
        )

    return None
