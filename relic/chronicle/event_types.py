"""
Chronicle Event Type Catalogue.

Canonical vocabulary for Chronicle events emitted by the Hermes adapter
and Relic governance layers. This file is the source of truth for
event_type values used in Chronicle events.

Reference: docs/architecture/hermes-current-state.md
Schema: relic.chronicle.schema.Event

Categories:
- runtime: Hermes runtime boundary events
- governance: Relic governance decisions
- identity: Identity mapping and consent events
- context: Context pack admission/block events
- output: Output review and transformation events
- delivery: Proactive delivery decisions
- handoff: Session handoff events
- approval: Approval request/resolution events
- cron: Cron/watcher scheduler events
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from relic.chronicle.enums import EventCategory as ChronicleEventCategory


class EventCategory(str, Enum):
    """Domain-level event category for grouping/filtering. NOT Chronicle storage category.
    Use CHRONICLE_CATEGORY_MAP to get the real ChronicleEventCategory for Event construction."""
    RUNTIME = "runtime"
    GOVERNANCE = "governance"
    IDENTITY = "identity"
    CONTEXT = "context"
    OUTPUT = "output"
    DELIVERY = "delivery"
    HANDOFF = "handoff"
    APPROVAL = "approval"
    CRON = "cron"
    SAFETY = "safety"
    PRIVACY = "privacy"


CHRONICLE_CATEGORY_MAP: dict[EventCategory, ChronicleEventCategory] = {
    EventCategory.RUNTIME: ChronicleEventCategory.BACKGROUND,
    EventCategory.GOVERNANCE: ChronicleEventCategory.DECISION,
    EventCategory.IDENTITY: ChronicleEventCategory.CONSENT,
    EventCategory.CONTEXT: ChronicleEventCategory.MEMORY,
    EventCategory.OUTPUT: ChronicleEventCategory.MODEL,
    EventCategory.DELIVERY: ChronicleEventCategory.BACKGROUND,
    EventCategory.HANDOFF: ChronicleEventCategory.DECISION,
    EventCategory.APPROVAL: ChronicleEventCategory.DECISION,
    EventCategory.CRON: ChronicleEventCategory.BACKGROUND,
    EventCategory.SAFETY: ChronicleEventCategory.SAFETY,
    EventCategory.PRIVACY: ChronicleEventCategory.PRIVACY,
}

_SENSITIVITY_TO_PRIVACY_LEVEL: dict[str, str] = {
    "safe": "safe",
    "pii": "s2",
    "sensitive": "s1",
    "secret": "s0",
}


@dataclass(frozen=True)
class EventType:
    """
    Canonical event type definition.

    Attributes:
        name: snake_case event type identifier
        category: Event category for grouping
        description: Human-readable description
        payload_schema: Optional dict describing expected payload fields
        sensitivity: Default sensitivity level (safe, pii, sensitive, secret)
        retention: Default retention policy
    """
    name: str
    category: EventCategory
    description: str
    payload_schema: Optional[dict] = None
    sensitivity: str = "safe"
    retention: str = "standard_365d"


# =============================================================================
# RUNTIME EVENTS
# =============================================================================

RUNTIME_EVENTS = [
    EventType(
        name="runtime_received",
        category=EventCategory.RUNTIME,
        description="Hermes runtime envelope received at boundary",
        payload_schema={
            "platform": "string",
            "session_id": "string|null",
            "chat_id": "string|null",
            "turn_index": "integer|null",
        },
        sensitivity="safe",
    ),
    EventType(
        name="identity_resolved",
        category=EventCategory.RUNTIME,
        description="Sender identity mapped to subject reference",
        payload_schema={
            "mapping_strategy": "string",
            "consent_required": "boolean",
            "consent_granted": "boolean",
        },
        sensitivity="pii",
    ),
    EventType(
        name="session_key_bound",
        category=EventCategory.RUNTIME,
        description="Session key hash bound to envelope",
        payload_schema={
            "hash_algorithm": "string",
            "scope_resolved": "boolean",
        },
        sensitivity="safe",
    ),
    EventType(
        name="tool_call_observed",
        category=EventCategory.RUNTIME,
        description="Hermes tool call observed at boundary",
        payload_schema={
            "tool_name": "string",
            "tool_call_id": "string",
        },
        sensitivity="safe",
    ),
]

# =============================================================================
# GOVERNANCE EVENTS
# =============================================================================

GOVERNANCE_EVENTS = [
    EventType(
        name="source_policy_checked",
        category=EventCategory.GOVERNANCE,
        description="Source class taxonomy check performed",
        payload_schema={
            "source_class": "string",
            "is_evidence_eligible": "boolean",
        },
        sensitivity="safe",
    ),
    EventType(
        name="context_pack_requested",
        category=EventCategory.GOVERNANCE,
        description="PromptContextPack build requested",
        payload_schema={
            "subject_ref": "string",
            "session_id": "string|null",
        },
        sensitivity="safe",
    ),
    EventType(
        name="context_item_admitted",
        category=EventCategory.GOVERNANCE,
        description="Context item admitted to pack",
        payload_schema={
            "item_type": "string",
            "item_hash": "string",
            "admission_reason": "string",
        },
        sensitivity="safe",
    ),
    EventType(
        name="context_item_blocked",
        category=EventCategory.GOVERNANCE,
        description="Context item blocked from pack",
        payload_schema={
            "item_type": "string",
            "block_reason": "string",
            "policy_ref": "string",
        },
        sensitivity="safe",
    ),
    EventType(
        name="context_pack_rendered",
        category=EventCategory.GOVERNANCE,
        description="PromptContextPack rendered for injection",
        payload_schema={
            "item_count": "integer",
            "blocked_count": "integer",
            "pack_hash": "string",
        },
        sensitivity="safe",
    ),
    EventType(
        name="delivery_decision_made",
        category=EventCategory.GOVERNANCE,
        description="Delivery gate decision rendered",
        payload_schema={
            "decision": "string",
            "reason_codes": "array",
            "platform": "string",
        },
        sensitivity="safe",
    ),
]

# =============================================================================
# IDENTITY EVENTS
# =============================================================================

IDENTITY_EVENTS = [
    EventType(
        name="consent_granted",
        category=EventCategory.IDENTITY,
        description="User granted consent for multi-chat mapping",
        payload_schema={
            "consent_key": "string",
            "platform": "string",
        },
        sensitivity="pii",
    ),
    EventType(
        name="consent_revoked",
        category=EventCategory.IDENTITY,
        description="User revoked consent for multi-chat mapping",
        payload_schema={
            "consent_key": "string",
            "platform": "string",
        },
        sensitivity="pii",
    ),
    EventType(
        name="explicit_mapping_registered",
        category=EventCategory.IDENTITY,
        description="Explicit sender→subject mapping registered",
        payload_schema={
            "mapping_key": "string",
            "platform": "string",
        },
        sensitivity="pii",
    ),
]

# =============================================================================
# OUTPUT EVENTS
# =============================================================================

OUTPUT_EVENTS = [
    EventType(
        name="output_reviewed",
        category=EventCategory.OUTPUT,
        description="OutputCritic reviewed LLM output",
        payload_schema={
            "critic_result": "string",
            "issues_found": "array",
        },
        sensitivity="safe",
    ),
    EventType(
        name="output_blocked",
        category=EventCategory.OUTPUT,
        description="Output blocked by critic or clinical filter",
        payload_schema={
            "block_reason": "string",
            "replacement_used": "string|null",
        },
        sensitivity="safe",
    ),
    EventType(
        name="output_transformed",
        category=EventCategory.OUTPUT,
        description="Output transformed by hook",
        payload_schema={
            "transformation_type": "string",
            "original_hash": "string",
            "transformed_hash": "string",
        },
        sensitivity="safe",
    ),
    EventType(
        name="escalation_notified",
        category=EventCategory.SAFETY,
        description="Safety escalation triggered",
        payload_schema={
            "escalation_type": "string",
            "severity": "string",
        },
        sensitivity="sensitive",
    ),
]

# =============================================================================
# HANDOFF EVENTS
# =============================================================================

HANDOFF_EVENTS = [
    EventType(
        name="handoff_requested",
        category=EventCategory.HANDOFF,
        description="Session handoff requested via /handoff",
        payload_schema={
            "source_session_id": "string",
            "target_profile_id": "string",
            "reason": "string",
        },
        sensitivity="pii",
    ),
    EventType(
        name="handoff_authorized",
        category=EventCategory.HANDOFF,
        description="Handoff authorized by gate",
        payload_schema={
            "handoff_id": "string",
            "policy_snapshot_ref": "string",
            "context_preserved": "boolean",
        },
        sensitivity="pii",
    ),
    EventType(
        name="handoff_blocked",
        category=EventCategory.HANDOFF,
        description="Handoff blocked by gate",
        payload_schema={
            "block_reason": "string",
            "risk_boundary_crossed": "boolean",
        },
        sensitivity="pii",
    ),
]

# =============================================================================
# APPROVAL EVENTS
# =============================================================================

APPROVAL_EVENTS = [
    EventType(
        name="approval_requested",
        category=EventCategory.APPROVAL,
        description="Approval requested for action",
        payload_schema={
            "approval_type": "string",
            "action_description": "string",
            "risk_level": "string",
        },
        sensitivity="safe",
    ),
    EventType(
        name="approval_granted",
        category=EventCategory.APPROVAL,
        description="Approval granted",
        payload_schema={
            "approval_id": "string",
            "granted_by": "string",
        },
        sensitivity="safe",
    ),
    EventType(
        name="approval_denied",
        category=EventCategory.APPROVAL,
        description="Approval denied",
        payload_schema={
            "approval_id": "string",
            "denial_reason": "string",
        },
        sensitivity="safe",
    ),
]

# =============================================================================
# CRON EVENTS
# =============================================================================

CRON_EVENTS = [
    EventType(
        name="proactive_checkin_scheduled",
        category=EventCategory.CRON,
        description="Proactive check-in scheduled",
        payload_schema={
            "schedule_id": "string",
            "facet": "string",
            "scheduled_time": "string",
        },
        sensitivity="safe",
    ),
    EventType(
        name="proactive_message_delivered",
        category=EventCategory.CRON,
        description="Proactive message delivered",
        payload_schema={
            "message_hash": "string",
            "media_type": "string",
            "delivery_decision_ref": "string",
        },
        sensitivity="safe",
    ),
    EventType(
        name="proactive_message_blocked",
        category=EventCategory.CRON,
        description="Proactive message blocked by gate",
        payload_schema={
            "block_reason": "string",
            "quiet_hours_active": "boolean",
        },
        sensitivity="safe",
    ),
    EventType(
        name="cron_decision_made",
        category=EventCategory.CRON,
        description="Cron/watcher decision rendered",
        payload_schema={
            "decision": "string",
            "reason_codes": "array",
            "candidate_message_hash": "string",
        },
        sensitivity="safe",
    ),
]

# =============================================================================
# CATALOGUE
# =============================================================================

EVENT_TYPE_CATALOGUE = {
    et.name: et
    for et in (
        RUNTIME_EVENTS
        + GOVERNANCE_EVENTS
        + IDENTITY_EVENTS
        + OUTPUT_EVENTS
        + HANDOFF_EVENTS
        + APPROVAL_EVENTS
        + CRON_EVENTS
    )
}


def get_event_type(name: str) -> EventType | None:
    """
    Get event type definition by name.

    Args:
        name: Event type name (snake_case)

    Returns:
        EventType definition or None if not found
    """
    return EVENT_TYPE_CATALOGUE.get(name)


def get_event_types_by_category(category: EventCategory) -> list[EventType]:
    """
    Get all event types in a category.

    Args:
        category: Event category

    Returns:
        List of EventType definitions
    """
    return [et for et in EVENT_TYPE_CATALOGUE.values() if et.category == category]


def validate_event_type(name: str) -> bool:
    """
    Validate event type name against catalogue.

    Args:
        name: Event type name to validate

    Returns:
        True if valid, False otherwise
    """
    return name in EVENT_TYPE_CATALOGUE


def get_catalogue_summary() -> dict:
    """
    Get catalogue summary for documentation.

    Returns:
        Dict with category counts and total
    """
    summary = {
        "total": len(EVENT_TYPE_CATALOGUE),
        "by_category": {},
    }
    for category in EventCategory:
        count = len(get_event_types_by_category(category))
        if count > 0:
            summary["by_category"][category.value] = count
    return summary
