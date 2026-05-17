"""
Hooks Adapter Wrapper — Integrates relic.hermes_adapter with existing hooks.

This module wraps the existing hooks.py with the Hermes Adapter,
adding Chronicle event emission for all governance decisions.

Design: Hermes is runtime. Relic is governance.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from relic.hermes_adapter import (
    HookAdapter,
    HermesRuntimeEnvelope,
    get_adapter,
)
from relic.hermes_adapter.chronicle_helper import (
    emit_governance_event,
    emit_output_event,
)

logger = logging.getLogger(__name__)

# Get the shared adapter instance
_adapter: Optional[HookAdapter] = None


def get_hermes_adapter() -> HookAdapter:
    """Get or create the Hermes adapter for hooks."""
    global _adapter
    if _adapter is None:
        _adapter = HookAdapter(emit_events=True)
    return _adapter


def pre_llm_call_adapter(
    *,
    session_id: str = "",
    user_message: str = "",
    conversation_history: list | None = None,
    is_first_turn: bool = False,
    model: str = "",
    platform: str = "",
    sender_id: str = "",
    chat_id: Optional[str] = None,
    hermes_profile_id: str = "default",
    gumi_instance_id: str = "default",
    **kwargs: Any,
) -> dict | None:
    """
    Adapter-enhanced pre_llm_call with Chronicle event emission.

    This wrapper:
    1. Creates HermesRuntimeEnvelope from hook kwargs
    2. Emits context_pack_requested event
    3. Wraps the original pre_llm_call logic
    4. Emits context_item_admitted/blocked events
    5. Emits context_pack_rendered event

    Args:
        session_id: Hermes session ID
        user_message: User message text
        conversation_history: Conversation history
        is_first_turn: Whether this is the first turn
        model: Model identifier
        platform: Platform identifier
        sender_id: Sender/user ID
        chat_id: Chat/thread ID (optional)
        hermes_profile_id: Hermes profile ID
        gumi_instance_id: Gumi instance ID
        **kwargs: Additional Hermes kwargs

    Returns:
        dict with context string or None
    """
    adapter = get_hermes_adapter()

    # Create envelope from Hermes kwargs
    envelope = adapter.create_envelope_from_hermes(
        session_id=session_id,
        chat_id=chat_id,
        platform=platform,
        sender_id=sender_id,
        hermes_profile_id=hermes_profile_id,
        gumi_instance_id=gumi_instance_id,
        model=model,
        message_content=user_message,
        **kwargs,
    )

    # Import original pre_llm_call logic
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

        # Fetch recent markers
        raw_markers: list[dict] = []
        try:
            from relic.shared_continuity.service import get_continuity_service
            svc = get_continuity_service()
            raw_markers = svc.recent_markers(subject_id=subject_id, limit=20) or []
            if raw_markers and hasattr(raw_markers[0], "__dict__"):
                raw_markers = [m.__dict__ for m in raw_markers]
        except Exception:
            raw_markers = []

        # Emit context_pack_requested event
        adapter.emit_context_pack_requested(envelope)

        # Run ContinuityAdmissionPolicy
        policy = get_admission_policy()
        decisions = policy.evaluate_markers(raw_markers)

        admitted_markers = [
            raw_markers[i]
            for i, d in enumerate(decisions)
            if d.admitted and i < len(raw_markers)
        ]
        blocked_decisions = [d for d in decisions if not d.admitted]

        # Emit admission/block events
        for marker in admitted_markers:
            adapter.emit_context_item_admitted(
                envelope,
                item_type="continuity_marker",
                item_hash=marker.get("marker_id", ""),
                admission_reason="policy_approved",
            )

        for decision in blocked_decisions:
            adapter.emit_context_item_blocked(
                envelope,
                item_type="continuity_marker",
                block_reason=decision.reason or decision.blocked_by or "admission_policy",
                policy_ref="continuity_admission_policy",
            )

        # Build PromptContextPack
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

        # Emit context_pack_rendered event
        import hashlib
        pack_hash = f"sha256:{hashlib.sha256(injected.encode()).hexdigest()[:32]}"
        adapter.emit_context_pack_rendered(
            envelope,
            item_count=len(continuity_items),
            blocked_count=len(blocked_items),
            pack_hash=pack_hash,
        )

        return {"context": injected}

    except Exception as exc:
        logger.warning("pre_llm_call_adapter hook failed (fail-closed): %s", type(exc).__name__)
        return None
    finally:
        # Safety signal scan — fire-and-forget
        if user_message:
            _run_safety_scan_adapter(
                envelope=envelope,
                user_message=user_message,
            )


def _run_safety_scan_adapter(
    envelope: HermesRuntimeEnvelope,
    user_message: str,
) -> None:
    """Extract safety signals and emit escalation events."""
    if not envelope.subject_ref or not user_message:
        return
    try:
        from relic.patterns.signal_extractor import SafetySignalExtractor
        from relic.safety.escalation_notifier import notify_escalation

        extractor = SafetySignalExtractor()
        result = extractor.extract(
            subject_id=envelope.subject_ref,
            gumi_instance_id=envelope.gumi_instance_id,
            hermes_profile_id=envelope.hermes_profile_id,
            events=[{"text": user_message, "event_id": f"{envelope.session_id}-turn"}],
        )

        if result.crisis_bypassed and result.crisis_signal_type:
            notify_escalation(envelope.subject_ref, result.crisis_signal_type)
            return

        for signal in result.signals:
            if signal.confidence >= 0.55:
                notify_escalation(envelope.subject_ref, signal.signal_family)

    except Exception as exc:
        logger.warning("_run_safety_scan_adapter failed (ignored): %s", type(exc).__name__)


def transform_llm_output_adapter(
    output: Optional[str] = None,
    session_id: str = "",
    sender_id: str = "",
    platform: str = "",
    hermes_profile_id: str = "default",
    gumi_instance_id: str = "default",
    **kwargs: Any,
) -> str | None:
    """
    Adapter-enhanced transform_llm_output with Chronicle event emission.

    This wrapper:
    1. Creates envelope from hook kwargs
    2. Runs OutputCritic
    3. Emits output_reviewed/blocked/transformed events

    Args:
        output: LLM output text
        session_id: Hermes session ID
        sender_id: Sender/user ID
        platform: Platform identifier
        hermes_profile_id: Hermes profile ID
        gumi_instance_id: Gumi instance ID
        **kwargs: Additional Hermes kwargs

    Returns:
        None (pass-through) or replacement string
    """
    if output is None:
        return None

    adapter = get_hermes_adapter()

    # Create envelope
    envelope = adapter.create_envelope_from_hermes(
        session_id=session_id,
        platform=platform,
        sender_id=sender_id,
        hermes_profile_id=hermes_profile_id,
        gumi_instance_id=gumi_instance_id,
        message_content=output,
    )

    text = str(output)

    # Import original OutputCritic logic
    FORBIDDEN_OUTPUT_TERMS = [
        "bipolar", "mania", "hypomania", "depression",
        "episode", "symptom", "diagnosis", "relapse", "pathology",
        "I detected a pattern", "the system noticed", "Relic detected"
    ]
    _SILENT = "[SILENT]"

    # Run OutputCritic
    critic_result = "pass"
    issues_found: list[str] = []

    try:
        from relic.gumi_plugin.critic import OutputCritic
        verdict = OutputCritic().review(text, consensual=True)
        
        if not verdict.allow:
            critic_result = verdict.reason
            issues_found.append(verdict.reason)
            
            if verdict.reason == "false_physical_experience":
                adapter.emit_output_blocked(envelope, "false_physical_experience", _SILENT)
                return _SILENT
            
            # dependency/need claim
            replacement = (
                "I'm here with you in this. "
                "What would feel most helpful right now?"
            )
            adapter.emit_output_blocked(envelope, verdict.reason, replacement)
            return replacement
    except Exception:
        pass

    # Fallback: clinical term filter
    lower = text.lower()
    hits = [term for term in FORBIDDEN_OUTPUT_TERMS if term.lower() in lower]
    if hits:
        critic_result = "clinical_terms_filtered"
        issues_found.extend(hits)
        replacement = (
            "I will keep this in your words, without putting labels on it. "
            "If you want, we can just hold onto the thread and come back to it gently."
        )
        adapter.emit_output_transformed(
            envelope,
            transformation_type="clinical_term_filter",
            original_content=text,
            transformed_content=replacement,
        )
        return replacement

    # Emit output_reviewed event (pass-through)
    adapter.emit_output_reviewed(envelope, critic_result, issues_found)

    return None


def post_llm_call_adapter(
    *,
    session_id: str = "",
    output: str = "",
    **kwargs: Any,
) -> None:
    """
    Adapter-enhanced post_llm_call observer.

    Currently a no-op, but provides extension point for future
    Chronicle event emission (e.g., turn completion events).
    """
    return None
