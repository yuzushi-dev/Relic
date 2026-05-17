"""
Hook Adapter — Wrapper for Hermes hooks with Chronicle event emission.

This module provides adapter wrappers around the Hermes hook entrypoint,
emitting canonical Chronicle events for:
- Context pack requests and admission
- Output review and transformation
- Safety escalations

Design: Hermes is runtime. Relic is governance.
"""

from __future__ import annotations

import hashlib
import logging
import threading
import uuid
from typing import Any, Optional
from uuid import UUID

_logger = logging.getLogger(__name__)

from relic.hermes_adapter.envelope import HermesRuntimeEnvelope, MetadataRedactionStatus
from relic.hermes_adapter.identity import IdentityMapper, MappingStrategy, ConsentRequiredError
from relic.hermes_adapter.chronicle_helper import (
    emit_runtime_event,
    emit_governance_event,
    emit_output_event,
)


def _compute_hash(value: str) -> str:
    """Compute SHA-256 hash of string."""
    return f"sha256:{hashlib.sha256(value.encode()).hexdigest()[:32]}"


class HookAdapter:
    """Adapter for Hermes hooks with Chronicle event emission."""

    def __init__(
        self,
        identity_mapper: Optional[IdentityMapper] = None,
        emit_events: bool = True,
    ):
        self.identity_mapper = identity_mapper or IdentityMapper()
        self.emit_events = emit_events

    def create_envelope_from_hermes(
        self,
        *,
        session_id: Optional[str] = None,
        chat_id: Optional[str] = None,
        platform: Optional[str] = None,
        sender_id: Optional[str] = None,
        hermes_profile_id: str,
        gumi_instance_id: str,
        model: Optional[str] = None,
        turn_index: Optional[int] = None,
        tool_call_id: Optional[str] = None,
        message_content: Optional[str] = None,
        **kwargs: Any,
    ) -> HermesRuntimeEnvelope:
        """Create HermesRuntimeEnvelope from Hermes hook kwargs."""
        trace_id = str(uuid.uuid4())

        subject_ref = None
        sender_ref = None
        if sender_id and platform:
            try:
                mapping = self.identity_mapper.map_sender_to_subject(
                    sender_id=sender_id,
                    platform=platform,
                    gumi_instance_id=gumi_instance_id,
                    hermes_profile_id=hermes_profile_id,
                    chat_id=chat_id,
                )
                subject_ref = mapping.subject_ref
                sender_ref = mapping.sender_ref

                if self.emit_events:
                    emit_runtime_event(
                        HermesRuntimeEnvelope(trace_id=trace_id),
                        "identity_resolved",
                        {
                            "mapping_strategy": mapping.mapping_strategy.value,
                            "consent_required": mapping.consent_required,
                            "consent_granted": mapping.consent_granted,
                        },
                    )
            except ConsentRequiredError:
                raise
            except Exception as exc:
                _logger.warning("Identity mapping failed: %s", exc)

        message_hash = None
        if message_content:
            message_hash = _compute_hash(message_content)

        envelope = HermesRuntimeEnvelope(
            trace_id=trace_id,
            session_id=session_id,
            chat_id=chat_id,
            platform=platform,
            sender_ref=sender_ref,
            subject_ref=subject_ref,
            hermes_profile_id=hermes_profile_id,
            gumi_instance_id=gumi_instance_id,
            model=model,
            turn_index=turn_index,
            tool_call_id=tool_call_id,
            message_hash=message_hash,
        )

        if self.emit_events:
            emit_runtime_event(envelope, "runtime_received")

        return envelope

    def emit_context_pack_requested(self, envelope: HermesRuntimeEnvelope) -> None:
        """Emit context pack requested event."""
        if not self.emit_events or not envelope.subject_ref:
            return

        emit_governance_event(
            subject_ref=envelope.subject_ref,
            event_type="context_pack_requested",
            payload={
                "session_id": envelope.session_id,
                "trace_id": envelope.trace_id,
            },
            session_id=uuid.UUID(envelope.session_id) if envelope.session_id else None,
            trace_id=uuid.UUID(envelope.trace_id) if envelope.trace_id else None,
        )

    def emit_context_item_admitted(
        self,
        envelope: HermesRuntimeEnvelope,
        item_type: str,
        item_hash: str,
        admission_reason: str,
    ) -> None:
        """Emit context item admitted event."""
        if not self.emit_events or not envelope.subject_ref:
            return

        emit_governance_event(
            subject_ref=envelope.subject_ref,
            event_type="context_item_admitted",
            payload={
                "item_type": item_type,
                "item_hash": item_hash,
                "admission_reason": admission_reason,
            },
            trace_id=uuid.UUID(envelope.trace_id) if envelope.trace_id else None,
        )

    def emit_context_item_blocked(
        self,
        envelope: HermesRuntimeEnvelope,
        item_type: str,
        block_reason: str,
        policy_ref: Optional[str] = None,
    ) -> None:
        """Emit context item blocked event."""
        if not self.emit_events or not envelope.subject_ref:
            return

        emit_governance_event(
            subject_ref=envelope.subject_ref,
            event_type="context_item_blocked",
            payload={
                "item_type": item_type,
                "block_reason": block_reason,
                "policy_ref": policy_ref or "default",
            },
            trace_id=uuid.UUID(envelope.trace_id) if envelope.trace_id else None,
        )

    def emit_context_pack_rendered(
        self,
        envelope: HermesRuntimeEnvelope,
        item_count: int,
        blocked_count: int,
        pack_hash: str,
    ) -> None:
        """Emit context pack rendered event."""
        if not self.emit_events or not envelope.subject_ref:
            return

        emit_governance_event(
            subject_ref=envelope.subject_ref,
            event_type="context_pack_rendered",
            payload={
                "item_count": item_count,
                "blocked_count": blocked_count,
                "pack_hash": pack_hash,
            },
            trace_id=uuid.UUID(envelope.trace_id) if envelope.trace_id else None,
        )

    def emit_output_reviewed(
        self,
        envelope: HermesRuntimeEnvelope,
        critic_result: str,
        issues_found: list[str],
    ) -> None:
        """Emit output reviewed event."""
        if not self.emit_events or not envelope.subject_ref:
            return

        emit_output_event(
            subject_ref=envelope.subject_ref,
            event_type="output_reviewed",
            payload={
                "critic_result": critic_result,
                "issues_found": issues_found,
            },
            trace_id=uuid.UUID(envelope.trace_id) if envelope.trace_id else None,
        )

    def emit_output_blocked(
        self,
        envelope: HermesRuntimeEnvelope,
        block_reason: str,
        replacement_used: Optional[str] = None,
    ) -> None:
        """Emit output blocked event."""
        if not self.emit_events or not envelope.subject_ref:
            return

        emit_output_event(
            subject_ref=envelope.subject_ref,
            event_type="output_blocked",
            payload={
                "block_reason": block_reason,
                "replacement_used": replacement_used,
            },
            trace_id=uuid.UUID(envelope.trace_id) if envelope.trace_id else None,
        )

    def emit_output_transformed(
        self,
        envelope: HermesRuntimeEnvelope,
        transformation_type: str,
        original_content: str,
        transformed_content: str,
    ) -> None:
        """Emit output transformed event."""
        if not self.emit_events or not envelope.subject_ref:
            return

        emit_output_event(
            subject_ref=envelope.subject_ref,
            event_type="output_transformed",
            payload={
                "transformation_type": transformation_type,
                "original_hash": _compute_hash(original_content),
                "transformed_hash": _compute_hash(transformed_content),
            },
            trace_id=uuid.UUID(envelope.trace_id) if envelope.trace_id else None,
        )


_default_adapter: Optional[HookAdapter] = None
_adapter_lock = threading.Lock()


def get_adapter() -> HookAdapter:
    """Get or create default HookAdapter."""
    global _default_adapter
    if _default_adapter is None:
        with _adapter_lock:
            if _default_adapter is None:
                _default_adapter = HookAdapter()
    return _default_adapter


def create_envelope_from_hermes(**kwargs: Any) -> HermesRuntimeEnvelope:
    """Create envelope from Hermes kwargs using default adapter."""
    return get_adapter().create_envelope_from_hermes(**kwargs)
