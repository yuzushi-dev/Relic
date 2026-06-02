"""
Chronicle Helper, Adapter-side emitter for canonical Chronicle events.

Wraps relic.chronicle.emitter.emit_event with:
- canonical event type validation
- domain→Chronicle category mapping
- sensitivity→PrivacyLevel coercion
- async emission via ChronicleEmitQueue (RELIC_CHRONICLE_SYNC=true to disable)

Set RELIC_CHRONICLE_SYNC=true in tests or debugging to force synchronous emission.
"""

from __future__ import annotations

import os
import uuid
from typing import Any, Optional
from uuid import UUID

from relic.chronicle.emitter import emit_event as _emit_event_sync
from relic.chronicle.event_types import (
    CHRONICLE_CATEGORY_MAP,
    _SENSITIVITY_TO_PRIVACY_LEVEL,
    get_event_type,
    validate_event_type,
)
from relic.persistence import PrivacyLevel
from relic.hermes_adapter.envelope import HermesRuntimeEnvelope

_SYNC_MODE = os.environ.get("RELIC_CHRONICLE_SYNC", "").lower() == "true"


def _to_uuid(value: Any) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (ValueError, AttributeError):
        return None


def _privacy(sensitivity: str) -> PrivacyLevel:
    return PrivacyLevel(_SENSITIVITY_TO_PRIVACY_LEVEL.get(sensitivity, "safe"))


def _emit(category, **kwargs: Any) -> UUID:
    """Emit via async queue (default) or synchronously (RELIC_CHRONICLE_SYNC=true)."""
    if _SYNC_MODE:
        return _emit_event_sync(**kwargs)

    from relic.hermes_adapter.emit_queue import EmitTask, get_emit_queue
    task = EmitTask(category=category, fn=_emit_event_sync, kwargs=kwargs)
    get_emit_queue().submit(task)
    return uuid.uuid4()


def emit_runtime_event(
    envelope: HermesRuntimeEnvelope,
    event_type: str,
    payload: Optional[dict] = None,
    extra_tags: Optional[list[str]] = None,
) -> UUID:
    """Emit a runtime boundary event from a Hermes envelope."""
    if not validate_event_type(event_type):
        raise ValueError(f"Unknown event type: {event_type}")

    et = get_event_type(event_type)
    chronicle_cat = CHRONICLE_CATEGORY_MAP[et.category]

    tags = [f"platform:{envelope.platform or 'unknown'}"]
    if envelope.hermes_profile_id:
        tags.append(f"profile:{envelope.hermes_profile_id}")
    if extra_tags:
        tags.extend(extra_tags)

    event_payload = dict(payload or {})
    event_payload["envelope_schema_version"] = envelope.schema_version

    return _emit(
        chronicle_cat,
        event_type=event_type,
        event_category=chronicle_cat,
        source_module="relic.hermes_adapter",
        payload=event_payload,
        sensitivity=_privacy(et.sensitivity),
        retention_policy=et.retention,
        trace_id=_to_uuid(envelope.trace_id) or uuid.uuid4(),
        session_id=_to_uuid(envelope.session_id),
        subject_id=envelope.subject_ref,
        tags=tags,
    )


def emit_identity_event(
    subject_ref: str,
    event_type: str,
    payload: Optional[dict] = None,
    trace_id: Optional[UUID] = None,
) -> UUID:
    """Emit an identity / consent event."""
    if not validate_event_type(event_type):
        raise ValueError(f"Unknown event type: {event_type}")

    et = get_event_type(event_type)
    chronicle_cat = CHRONICLE_CATEGORY_MAP[et.category]

    return _emit(
        chronicle_cat,
        event_type=event_type,
        event_category=chronicle_cat,
        source_module="relic.hermes_adapter.identity",
        payload=dict(payload or {}),
        sensitivity=_privacy(et.sensitivity),
        retention_policy=et.retention,
        trace_id=trace_id or uuid.uuid4(),
        subject_id=subject_ref,
        tags=[f"subject:{subject_ref}"],
    )


def emit_governance_event(
    subject_ref: str,
    event_type: str,
    payload: Optional[dict] = None,
    session_id: Optional[UUID] = None,
    trace_id: Optional[UUID] = None,
) -> UUID:
    """Emit a governance decision event."""
    if not validate_event_type(event_type):
        raise ValueError(f"Unknown event type: {event_type}")

    et = get_event_type(event_type)
    chronicle_cat = CHRONICLE_CATEGORY_MAP[et.category]

    return _emit(
        chronicle_cat,
        event_type=event_type,
        event_category=chronicle_cat,
        source_module="relic.hermes_adapter.governance",
        payload=dict(payload or {}),
        sensitivity=_privacy(et.sensitivity),
        retention_policy=et.retention,
        trace_id=trace_id or uuid.uuid4(),
        session_id=session_id,
        subject_id=subject_ref,
        tags=[f"subject:{subject_ref}"],
    )


def emit_output_event(
    subject_ref: str,
    event_type: str,
    payload: Optional[dict] = None,
    trace_id: Optional[UUID] = None,
) -> UUID:
    """Emit an output review / transformation event."""
    if not validate_event_type(event_type):
        raise ValueError(f"Unknown event type: {event_type}")

    et = get_event_type(event_type)
    chronicle_cat = CHRONICLE_CATEGORY_MAP[et.category]

    return _emit(
        chronicle_cat,
        event_type=event_type,
        event_category=chronicle_cat,
        source_module="relic.hermes_adapter.output",
        payload=dict(payload or {}),
        sensitivity=_privacy(et.sensitivity),
        retention_policy=et.retention,
        trace_id=trace_id or uuid.uuid4(),
        subject_id=subject_ref,
        tags=[f"subject:{subject_ref}"],
    )
