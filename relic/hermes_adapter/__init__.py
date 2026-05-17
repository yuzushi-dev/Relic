"""
Hermes Adapter — Boundary layer between Hermes runtime and Relic governance.

Design principle: Hermes is runtime. Relic is governance.
"""

from relic.hermes_adapter.envelope import HermesRuntimeEnvelope, MetadataRedactionStatus
from relic.hermes_adapter.identity import IdentityMapper, SubjectMapping, MappingStrategy, ConsentRequiredError
from relic.hermes_adapter.hooks import HookAdapter, create_envelope_from_hermes, get_adapter
from relic.hermes_adapter.chronicle_helper import (
    emit_runtime_event,
    emit_identity_event,
    emit_governance_event,
    emit_output_event,
)
from relic.hermes_adapter.cron_bridge import (
    RuntimeDecisionResult,
    CronBridge,
    get_bridge,
    evaluate_proactive_delivery,
)
from relic.hermes_adapter.handoff_gate import (
    HandoffGate,
    HandoffRequest,
    HandoffDecision,
    HandoffRisk,
    get_handoff_gate,
    evaluate_handoff,
)
from relic.hermes_adapter.approvals import (
    ApprovalManager,
    ApprovalRequest,
    ApprovalResolution,
    ApprovalType,
    ApprovalDecision,
    RiskLevel,
    get_approval_manager,
    request_approval,
    resolve_approval,
)
from relic.hermes_adapter.observability import (
    ObservabilityBridge,
    RedactedSpan,
    RedactionLevel,
    get_observability_bridge,
)
from relic.hermes_adapter.prompt_cache import (
    PromptCachePolicy,
    CacheKey,
    CacheInvalidation,
    CacheSection,
    CacheInvalidationReason,
    get_cache_policy,
)
from relic.hermes_adapter.source_policy import (
    SourcePolicy,
    SourceClass,
    SourceClassification,
    ConsentState,
    get_source_policy,
    classify_source,
    check_evidence_eligibility,
)
from relic.hermes_adapter.policy_gate import PolicyGate, PolicyDecision, ReasonCode
from relic.hermes_adapter.state_store import StateStore
from relic.hermes_adapter.emit_queue import ChronicleEmitQueue, get_emit_queue

__version__ = "0.4.1"

__all__ = [
    # Envelope
    "HermesRuntimeEnvelope",
    "MetadataRedactionStatus",
    # Identity
    "IdentityMapper",
    "SubjectMapping",
    "MappingStrategy",
    "ConsentRequiredError",
    # Hooks
    "HookAdapter",
    "create_envelope_from_hermes",
    "get_adapter",
    # Chronicle helpers
    "emit_runtime_event",
    "emit_identity_event",
    "emit_governance_event",
    "emit_output_event",
    # Cron bridge
    "RuntimeDecisionResult",
    "CronBridge",
    "get_bridge",
    "evaluate_proactive_delivery",
    # Handoff gate
    "HandoffGate",
    "HandoffRequest",
    "HandoffDecision",
    "HandoffRisk",
    "get_handoff_gate",
    "evaluate_handoff",
    # Approvals
    "ApprovalManager",
    "ApprovalRequest",
    "ApprovalResolution",
    "ApprovalType",
    "ApprovalDecision",
    "RiskLevel",
    "get_approval_manager",
    "request_approval",
    "resolve_approval",
    # Observability
    "ObservabilityBridge",
    "RedactedSpan",
    "RedactionLevel",
    "get_observability_bridge",
    # Prompt cache
    "PromptCachePolicy",
    "CacheKey",
    "CacheInvalidation",
    "CacheSection",
    "CacheInvalidationReason",
    "get_cache_policy",
    # Source policy
    "SourcePolicy",
    "SourceClass",
    "SourceClassification",
    "ConsentState",
    "get_source_policy",
    "classify_source",
    "check_evidence_eligibility",
    # Policy gate base
    "PolicyGate",
    "PolicyDecision",
    "ReasonCode",
    # State store
    "StateStore",
    # Emit queue
    "ChronicleEmitQueue",
    "get_emit_queue",
]
