# Hermes Adapter Reference

> **Version**: 0.4.0  
> **Status**: Implemented (2026-05-16)  
> **Package**: `relic.hermes_adapter`

---

## Overview

The Hermes Adapter provides a formal façade between Hermes runtime and Relic governance layers.

**Design Principle**: Hermes is runtime. Relic is governance.

---

## Package Structure

```
relic/hermes_adapter/
├── __init__.py              # Public exports
├── envelope.py              # HermesRuntimeEnvelope
├── identity.py              # IdentityMapper, SubjectMapping
├── hooks.py                 # HookAdapter
├── chronicle_helper.py      # Chronicle event emission helpers
├── cron_bridge.py           # CronBridge, RuntimeDecisionResult
├── handoff_gate.py          # HandoffGate, HandoffDecision
├── approvals.py             # ApprovalManager
├── observability.py         # ObservabilityBridge
├── prompt_cache.py          # PromptCachePolicy
└── source_policy.py         # SourcePolicy
```

---

## Core Components

### HermesRuntimeEnvelope

Normalized runtime metadata boundary object.

```python
from relic.hermes_adapter import HermesRuntimeEnvelope

envelope = HermesRuntimeEnvelope(
    trace_id="trace-123",
    session_id="session-abc",
    platform="telegram",
    sender_ref="hashed-sender",
    subject_ref="hashed-subject",
    hermes_profile_id="profile-default",
    gumi_instance_id="gumi-main",
    metadata_redaction_status=MetadataRedactionStatus.HASH_ONLY,
)
```

**Fields**:
- `schema_version`: "relic.hermes_runtime_envelope.v1"
- `trace_id`: Unique trace identifier (min 8 chars)
- `session_id`: Hermes session ID
- `chat_id`: Chat/thread ID
- `platform`: Platform identifier
- `sender_ref`: Hashed sender reference
- `subject_ref`: Subject reference for Relic
- `hermes_profile_id`: Hermes profile ID
- `gumi_instance_id`: Gumi instance ID
- `model`: Model identifier
- `turn_index`: Turn number (0-based)
- `tool_call_id`: Tool call identifier
- `message_ref`: Message reference
- `message_hash`: SHA-256 hash of content
- `received_at`: UTC timestamp
- `metadata_redaction_status`: Redaction level
- `session_key_hash`: Optional session key hash

---

### IdentityMapper

Maps Hermes identifiers to Relic subject references.

```python
from relic.hermes_adapter import IdentityMapper, MappingStrategy

mapper = IdentityMapper(mapping_strategy=MappingStrategy.HASHED)

mapping = mapper.map_sender_to_subject(
    sender_id="user123",
    platform="telegram",
    gumi_instance_id="gumi-main",
    hermes_profile_id="profile-default",
    chat_id="chat-001",  # For consent-based mapping
)

print(mapping.subject_ref)  # Hashed subject reference
print(mapping.sender_ref)   # Hashed sender reference
print(mapping.mapping_strategy)  # HASHED
```

**Mapping Strategies**:
- `HASHED`: Default, SHA-256 with platform/Gumi/Hermes scope
- `CONFIGURED`: Explicit sender→subject mappings
- `CONSENT_BASED`: Requires explicit consent for multi-chat
- `DIRECT`: Use sender_id as subject_ref (development only)

---

### HookAdapter

Wrapper for Hermes hooks with Chronicle event emission.

```python
from relic.hermes_adapter import HookAdapter

adapter = HookAdapter(emit_events=True)

# Create envelope from Hermes kwargs
envelope = adapter.create_envelope_from_hermes(
    session_id="session-123",
    platform="telegram",
    sender_id="user123",
    hermes_profile_id="profile-default",
    gumi_instance_id="gumi-main",
    message_content="Hello!",
)

# Emit context events
adapter.emit_context_pack_requested(envelope)
adapter.emit_context_item_admitted(envelope, "continuity_marker", "hash-abc", "policy_approved")
adapter.emit_context_item_blocked(envelope, "continuity_marker", "admission_policy", "policy_ref")
adapter.emit_context_pack_rendered(envelope, 5, 2, "pack-hash")

# Emit output events
adapter.emit_output_reviewed(envelope, "pass", [])
adapter.emit_output_blocked(envelope, "false_physical_experience", "[SILENT]")
adapter.emit_output_transformed(envelope, "clinical_term_filter", original, transformed)
```

---

### CronBridge

Bridge for cron-based proactive delivery decisions.

```python
from relic.hermes_adapter import CronBridge, RuntimeDecisionResult
from relic.hermes_runtime import RuntimeDecision

bridge = CronBridge(
    gumi_instance_id="gumi-main",
    hermes_profile_id="profile-default",
)

result = bridge.evaluate_proactive_delivery(
    subject_ref="subject-123",
    candidate_message="Good morning!",
    media_type="text",
)

print(result.decision)  # CANDIDATE or NO_REPLY
print(result.is_deliverable())  # True if CANDIDATE or DELIVER
```

**RuntimeDecisionResult Fields**:
- `decision`: RuntimeDecision enum
- `reason_codes`: List of reason codes
- `subject_ref`: Subject reference
- `candidate_message`: Optional message content
- `candidate_message_hash`: SHA-256 hash
- `media_type`: text/voice/image/music
- `trace_event_id`: Optional Chronicle event ID
- `gumi_instance_id`: Gumi instance
- `hermes_profile_id`: Hermes profile
- `decided_at`: UTC timestamp

---

### HandoffGate

Gatekeeper for Hermes /handoff operations.

```python
from relic.hermes_adapter import HandoffGate, HandoffRequest, HandoffDecisionValue

gate = HandoffGate(emit_events=True)

request = HandoffRequest(
    source_session_id="session-123",
    source_profile_id="profile-a",
    target_profile_id="profile-b",
    reason="User requested model change",
    preserve_context=True,
)

result = gate.evaluate(request, "subject-123")

print(result.decision)  # AUTHORIZED, BLOCKED, or REVIEW_REQUIRED
print(result.risk_level)  # LOW, MEDIUM, HIGH, CRITICAL
```

**Forbidden Handoffs** (default policy):
- Cross-subject handoff without explicit consent
- Handoff to untrusted model without review
- Handoff during active safety review
- Handoff that would lose correction state

---

### ApprovalManager

Manager for approval lifecycle.

```python
from relic.hermes_adapter import (
    ApprovalManager,
    ApprovalRequest,
    ApprovalResolution,
    ApprovalType,
    ApprovalDecision,
    RiskLevel,
)

manager = ApprovalManager(emit_events=True)

# Create request
request = ApprovalRequest.create(
    approval_type=ApprovalType.DELIVERY,
    action_description="Deliver proactive message",
    risk_level=RiskLevel.MEDIUM,
    subject_ref="subject-123",
)
manager.request(request)

# Resolve
resolution = ApprovalResolution(
    approval_id=request.approval_id,
    decision=ApprovalDecision.GRANTED,
    resolved_by="user",
)
manager.resolve(resolution)
```

**Approval Types**:
- `DELIVERY`: Proactive delivery approval
- `HANDOFF`: Session handoff approval
- `CONTEXT_EXPANSION`: Context pack expansion
- `TOOL_EXECUTION`: External tool execution
- `PROFILE_CHANGE`: Profile modification
- `DATA_EXPORT`: Data export request

---

### ObservabilityBridge

Bridge for exporting redacted observability data.

```python
from relic.hermes_adapter import ObservabilityBridge, RedactionLevel

bridge = ObservabilityBridge(
    redaction_level=RedactionLevel.REDACTED,
    export_enabled=False,  # Disabled by default
)

# Create span
span = bridge.create_span(
    trace_id="trace-123",
    name="model_call",
    attributes={"model": "gpt-4", "temperature": 0.7},
)

# End span
span = bridge.end_span(
    span,
    metrics={"latency_ms": 100, "tokens": 50},
)

# Export (if enabled)
bridge.export_span(span)
```

**Redaction Rules**:
- No raw user messages in spans
- No subject identifiers (use hashed references)
- No profile content summaries
- Only numeric metrics allowed
- Attributes must pass redaction filter

---

### PromptCachePolicy

Policy manager for Hermes prompt caching.

```python
from relic.hermes_adapter import (
    PromptCachePolicy,
    CacheSection,
    CacheInvalidationReason,
)

policy = PromptCachePolicy(
    default_ttl_seconds=3600,
    max_cache_size=10,
)

# Create cache key
key = policy.create_cache_key(
    subject_ref="subject-123",
    hermes_profile_id="profile-default",
    sections=[CacheSection.SYSTEM_INSTRUCTIONS, CacheSection.CONTEXT_PACK],
    policy_snapshot_hash="hash-abc",
    profile_version="v1.0",
)

# Check validity
is_valid = policy.is_valid(
    key,
    current_policy_hash="hash-abc",
    current_profile_version="v1.0",
)

# Invalidate
invalidation = policy.invalidate(
    subject_ref="subject-123",
    reason=CacheInvalidationReason.POLICY_CHANGED,
    old_policy_hash="hash-abc",
    new_policy_hash="hash-xyz",
)
```

**Cache Sections**:
- `SYSTEM_INSTRUCTIONS`: Cacheable
- `CONTEXT_PACK`: Cacheable
- `PROFILE_SUMMARY`: NOT cacheable (subject state)
- `MEMORY_HINTS`: Cacheable
- `STYLE_GUIDE`: Cacheable
- `SAFETY_RULES`: Cacheable

---

### SourcePolicy

Unified source-class taxonomy enforcer.

```python
from relic.hermes_adapter import (
    SourcePolicy,
    SourceClass,
    ConsentState,
    classify_source,
    check_evidence_eligibility,
)
from relic.hermes_adapter import HermesRuntimeEnvelope

# Classify source from envelope
envelope = HermesRuntimeEnvelope(
    sender_ref="sender-123",
    platform="telegram",
)
classification = classify_source(envelope)

print(classification.source_class)  # USER_DIRECT
print(classification.is_evidence_eligible)  # True

# Check eligibility with consent
is_eligible = check_evidence_eligibility(
    source_class=SourceClass.PUBLIC_WEB_SOURCE,
    consent_state=ConsentState.GRANTED,
    is_explicit_request=True,
)
```

**Source Classes**:
- `USER_DIRECT`: Direct user input (eligible)
- `USER_REQUESTED`: User-requested external (eligible with provenance)
- `SYSTEM_GENERATED`: System-generated context (eligible)
- `GUMI_DIEGETIC_EVENT`: Gumi diegetic event (NOT eligible by default)
- `PUBLIC_WEB_SOURCE`: Public web source (requires explicit request)
- `TOOL_EXECUTION_RESULT`: Tool result (eligible)
- `PROACTIVE_DELIVERY`: Proactive message (NOT eligible)
- `ADMIN_OVERRIDE`: Admin override (eligible with audit)

---

## Convenience Functions

All components provide singleton accessors:

```python
from relic.hermes_adapter import (
    get_adapter,
    get_bridge,
    get_handoff_gate,
    get_approval_manager,
    get_observability_bridge,
    get_cache_policy,
    get_source_policy,
)

# Use singletons
adapter = get_adapter()
bridge = get_bridge()
gate = get_handoff_gate()
```

---

## Event Emission Helpers

```python
from relic.hermes_adapter import (
    emit_runtime_event,
    emit_identity_event,
    emit_governance_event,
    emit_output_event,
)
from relic.hermes_adapter import HermesRuntimeEnvelope

envelope = HermesRuntimeEnvelope(trace_id="trace-123")

# Runtime events
emit_runtime_event(envelope, "runtime_received")
emit_runtime_event(envelope, "identity_resolved", {"strategy": "hashed"})

# Identity events
emit_identity_event("subject-123", "consent_granted", {"platform": "telegram"})

# Governance events
emit_governance_event("subject-123", "context_pack_requested", {"session_id": "s-123"})

# Output events
emit_output_event("subject-123", "output_reviewed", {"critic_result": "pass"})
```

---

## Testing

```bash
# Run adapter tests
pytest tests/hermes_compat/test_runtime_envelope.py -v
pytest tests/hermes_compat/test_chronicle_event_types.py -v
pytest tests/hermes_compat/test_cron_bridge.py -v
pytest tests/hermes_compat/test_phase567.py -v

# Run all Hermes compatibility tests
pytest tests/hermes_compat/ -v
```

---

## References

- `docs/architecture/hermes-current-state.md` — Integration context
- `docs/architecture/trace-ledger.md` — Chronicle trace ledger
- `relic/chronicle/schema.py` — Event schema
- `relic/hermes_runtime.py` — Runtime decision logic
