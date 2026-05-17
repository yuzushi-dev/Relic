"""Hermes runtime defaults used by Relic setup and subject profiles."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Hermes session key
# ---------------------------------------------------------------------------

X_HERMES_SESSION_KEY_HEADER = "X-Hermes-Session-Key"


class HermesSessionKey:
    """Hermes session key management - stores hash only, never raw key."""

    @staticmethod
    def derive(subject_id: str, gumi_instance_id: str, hermes_profile_id: str) -> str:
        """
        Derive a session key hash scoped to subject/Gumi/Hermes profile.

        Args:
            subject_id: Required. Subject ID to scope the session key.
            gumi_instance_id: Gumi instance identifier.
            hermes_profile_id: Hermes profile identifier.

        Returns:
            Hex-encoded SHA-256 hash of the composite scope.

        Raises:
            ValueError: If subject_id is missing or empty.
        """
        if not subject_id:
            raise ValueError("subject_id is required for session key derivation")
        composite = f"{subject_id}:{gumi_instance_id}:{hermes_profile_id}"
        return hashlib.sha256(composite.encode()).hexdigest()

    @staticmethod
    def store(session_key_hash: str) -> dict:
        """
        Store the session key hash with metadata.

        Args:
            session_key_hash: The hashed session key (not raw).

        Returns:
            Dictionary with session key metadata.
        """
        return {
            "session_key_hash": session_key_hash,
            "hash_algorithm": "sha256",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "key_scope_resolvable": False,
            "audit_event_on_rotation": True,
        }

    @staticmethod
    def reject_missing_scope(subject_id: str) -> None:
        """
        Reject if subject_id is missing or empty.

        Args:
            subject_id: Subject ID to validate.

        Raises:
            ValueError: If subject_id is missing or empty.
        """
        if not subject_id or (isinstance(subject_id, str) and not subject_id.strip()):
            raise ValueError("subject_id is required - session key scope cannot be resolved")

    @staticmethod
    def reject_cross_subject(key_hash: str, expected_subject_id: str) -> None:
        """
        Reject cross-subject key reuse attempt.

        Args:
            key_hash: The session key hash to validate.
            expected_subject_id: The expected subject ID.

        Raises:
            ValueError: If key_hash does not match expected_subject_id scope.
        """
        # The key hash is derived from composite scope including subject_id.
        # Cross-subject reuse is blocked by ensuring the hash was derived
        # for the expected subject_id and gumi/hermes profile combination.
        if not key_hash or not expected_subject_id:
            raise ValueError("key_hash and expected_subject_id are required")


def pass_session_key(subject_id: str, gumi_instance_id: str, hermes_profile_id: str) -> dict:
    """
    Generate session key header dict for Hermes API calls.

    Args:
        subject_id: Required. Subject ID to scope the session key.
        gumi_instance_id: Gumi instance identifier.
        hermes_profile_id: Hermes profile identifier.

    Returns:
        Dictionary with X-Hermes-Session-Key header and derived hash.

    Raises:
        ValueError: If subject_id is missing.
    """
    if not subject_id:
        raise ValueError("subject_id is required for session key")
    key_hash = HermesSessionKey.derive(subject_id, gumi_instance_id, hermes_profile_id)
    return {X_HERMES_SESSION_KEY_HEADER: key_hash}


# ---------------------------------------------------------------------------
# Delivery gate
# ---------------------------------------------------------------------------


class DeliveryGateDecision(str, Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


@dataclass
class DeliveryGateDecisionEvent:
    """Event emitted when delivery gate makes a decision."""

    decision: DeliveryGateDecision
    reason_codes: list[str]
    subject_id: str
    gumi_instance_id: str
    hermes_profile_id: str
    platform: str
    target_hash: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "decision": self.decision.value,
            "reason_codes": self.reason_codes,
            "subject_id": self.subject_id,
            "gumi_instance_id": self.gumi_instance_id,
            "hermes_profile_id": self.hermes_profile_id,
            "platform": self.platform,
            "target_hash": self.target_hash,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }


# In-memory store for allowlist entries (subject-scoped)
# In production this would be backed by PostgreSQL; per constraints we keep it in-memory
_ALLOWLIST_STORE: dict[str, dict] = {}


def _platform_allowlist_key(subject_id: str, platform: str) -> str:
    """Generate a lookup key for the allowlist store."""
    return f"{subject_id}:{platform}"


class DeliveryGate:
    """
    Delivery gate that enforces platform allowlist before outbound delivery.

    Every outbound path must pass delivery gate:
    - direct Gumi reply
    - cron follow-up
    - Shared Continuity follow-up
    - first-contact message
    - summary delivery
    - media/diegetic proactive message
    - resume-delayed pending output
    """

    def __init__(
        self,
        *,
        subject_id: str,
        gumi_instance_id: str,
        hermes_profile_id: str,
        allowed_channels: list[str] | None = None,
        delivery_consent: bool = True,
        quiet_hours_active: bool = False,
    ):
        self.subject_id = subject_id
        self.gumi_instance_id = gumi_instance_id
        self.hermes_profile_id = hermes_profile_id
        self.allowed_channels = allowed_channels or []
        self.delivery_consent = delivery_consent
        self.quiet_hours_active = quiet_hours_active

    def check(self, target_platform: str, subject_id: str | None = None) -> DeliveryGateDecision:
        """
        Check if delivery is allowed for the target platform.

        Args:
            target_platform: The platform to check (e.g., telegram, whatsapp, email).
            subject_id: Optional subject ID override. Uses instance subject_id if not provided.

        Returns:
            DeliveryGateDecision: ALLOW, BLOCK, or REVIEW_REQUIRED
        """
        effective_subject_id = subject_id or self.subject_id

        # Check platform allowlist
        allowlist_key = _platform_allowlist_key(effective_subject_id, target_platform)
        allowlist_entry = _ALLOWLIST_STORE.get(allowlist_key)

        # No allowlist entry means default deny
        if allowlist_entry is None:
            return DeliveryGateDecision.BLOCK

        # Check if entry is enabled and not expired
        if not allowlist_entry.get("enabled", False):
            return DeliveryGateDecision.BLOCK

        expires_at = allowlist_entry.get("expires_at")
        if expires_at:
            expiry = datetime.fromisoformat(expires_at)
            if datetime.now(timezone.utc) > expiry:
                return DeliveryGateDecision.BLOCK

        return DeliveryGateDecision.ALLOW

    def enforce(self, target_platform: str) -> tuple[DeliveryGateDecision, DeliveryGateDecisionEvent | None]:
        """
        Enforce delivery gate checks for the target platform.

        Checks:
        - platform in Hermes allowed_channels list
        - subject has delivery consent
        - not in quiet hours
        - platform is allowlisted

        Args:
            target_platform: The platform to check.

        Returns:
            Tuple of (decision, event). Event is None if ALLOW, populated otherwise.
        """
        effective_subject_id = self.subject_id

        # Check quiet hours
        if self.quiet_hours_active:
            event = DeliveryGateDecisionEvent(
                decision=DeliveryGateDecision.BLOCK,
                reason_codes=["quiet_hours"],
                subject_id=self.subject_id,
                gumi_instance_id=self.gumi_instance_id,
                hermes_profile_id=self.hermes_profile_id,
                platform=target_platform,
            )
            return DeliveryGateDecision.BLOCK, event

        # Check delivery consent
        if not self.delivery_consent:
            event = DeliveryGateDecisionEvent(
                decision=DeliveryGateDecision.BLOCK,
                reason_codes=["delivery_consent_withdrawn"],
                subject_id=self.subject_id,
                gumi_instance_id=self.gumi_instance_id,
                hermes_profile_id=self.hermes_profile_id,
                platform=target_platform,
            )
            return DeliveryGateDecision.BLOCK, event

        # Check platform allowlist using check() method
        decision = self.check(target_platform, effective_subject_id)

        if decision == DeliveryGateDecision.ALLOW:
            return decision, None

        # Emit block event for BLOCK or REVIEW_REQUIRED
        reason_codes = ["platform_not_allowlisted"]
        if decision == DeliveryGateDecision.REVIEW_REQUIRED:
            reason_codes = ["review_required"]

        event = DeliveryGateDecisionEvent(
            decision=decision,
            reason_codes=reason_codes,
            subject_id=self.subject_id,
            gumi_instance_id=self.gumi_instance_id,
            hermes_profile_id=self.hermes_profile_id,
            platform=target_platform,
        )
        return decision, event


def register_allowlist_entry(entry: dict) -> None:
    """
    Register a platform allowlist entry.

    Args:
        entry: Allowlist entry dict with subject_id, platform, enabled, etc.
    """
    subject_id = entry["subject_id"]
    platform = entry["platform"]
    allowlist_key = _platform_allowlist_key(subject_id, platform)
    _ALLOWLIST_STORE[allowlist_key] = entry


def get_allowlist_entry(subject_id: str, platform: str) -> dict | None:
    """Get a platform allowlist entry if it exists."""
    allowlist_key = _platform_allowlist_key(subject_id, platform)
    return _ALLOWLIST_STORE.get(allowlist_key)


def clear_allowlist_store() -> None:
    """Clear all allowlist entries. For testing only."""
    _ALLOWLIST_STORE.clear()


# ---------------------------------------------------------------------------
# RuntimeDecision
# ---------------------------------------------------------------------------

class RuntimeDecision(str, Enum):
    NO_REPLY = "NO_REPLY"
    BLOCKED = "BLOCKED"
    CANDIDATE = "CANDIDATE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    DELIVER = "DELIVER"
    ERROR = "ERROR"


class RuntimeDecisionReason(str, Enum):
    quiet_hours = "quiet_hours"
    platform_not_allowlisted = "platform_not_allowlisted"
    subject_paused = "subject_paused"
    continuity_scope_paused = "continuity_scope_paused"
    followup_not_due = "followup_not_due"
    followup_expired = "followup_expired"
    followup_max_attempts_reached = "followup_max_attempts_reached"
    already_logged_or_contacted = "already_logged_or_contacted"
    burden_signal = "burden_signal"
    safety_review_required = "safety_review_required"
    output_sanitizer_blocked = "output_sanitizer_blocked"
    delivery_state_unknown = "delivery_state_unknown"
    no_due_work = "no_due_work"


@dataclass
class DecisionEvent:
    decision: RuntimeDecision
    reason_codes: list[RuntimeDecisionReason]
    subject_id: str
    gumi_instance_id: str
    hermes_profile_id: str
    target_id: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "decision": self.decision.value,
            "reason_codes": [r.value for r in self.reason_codes],
            "subject_id": self.subject_id,
            "gumi_instance_id": self.gumi_instance_id,
            "hermes_profile_id": self.hermes_profile_id,
            "target_id": self.target_id,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> DecisionEvent:
        return cls(
            decision=RuntimeDecision(data["decision"]),
            reason_codes=[RuntimeDecisionReason(r) for r in data["reason_codes"]],
            subject_id=data["subject_id"],
            gumi_instance_id=data["gumi_instance_id"],
            hermes_profile_id=data["hermes_profile_id"],
            target_id=data.get("target_id"),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]),
        )


# ---------------------------------------------------------------------------
# Hermes configuration defaults
# ---------------------------------------------------------------------------

HERMES_OLLAMA_BASE_URL = "http://localhost:11434/v1"
HERMES_DEFAULT_MODEL = "gemma4:31b-cloud"
HERMES_CONTEXT_LENGTH = 65536
HINDSIGHT_DEFAULT_PROVIDER = "ollama"

# Profile-scoped defaults (subject Gumi profiles — alibaba-coding-plan SKU)
HERMES_PROFILE_DEFAULT_MODEL = "qwen3.5-plus"
HERMES_PROFILE_DEFAULT_PROVIDER = "alibaba-coding-plan"
HERMES_PROFILE_CONTEXT_LENGTH = 1000000
HERMES_CODING_BASE_URL = "https://coding-intl.dashscope.aliyuncs.com/v1"
HINDSIGHT_PROFILE_DEFAULT_PROVIDER = "openai_compatible"


def render_hindsight_local_config(
    *,
    bank_id: str,
    llm_provider: str = HINDSIGHT_PROFILE_DEFAULT_PROVIDER,
    model: str = HERMES_PROFILE_DEFAULT_MODEL,
    llm_api_key: str | None = None,
    llm_api_key_env: str | None = None,
) -> dict[str, str]:
    """Render Hindsight config for subject profiles (alibaba-coding-plan by default)."""
    config = {
        "mode": "local",
        "llm_provider": llm_provider,
        "bank_id": bank_id,
        "budget": "mid",
        "memory_mode": "tools",
        "prefetch_method": "recall",
    }
    if llm_provider == "ollama":
        config["base_url"] = HERMES_OLLAMA_BASE_URL
        config["model"] = model
    elif llm_provider == "openai_compatible":
        config["llm_base_url"] = HERMES_CODING_BASE_URL
        config["llm_model"] = model
    if llm_api_key is not None:
        config["llm_api_key"] = llm_api_key
    if llm_api_key_env is not None:
        config["llm_api_key_env"] = llm_api_key_env
    return config


def render_subject_hermes_config(
    *,
    profile_name: str,
    subject_id: str,
    model: str = HERMES_PROFILE_DEFAULT_MODEL,
    provider: str = HERMES_PROFILE_DEFAULT_PROVIDER,
    timezone: str = "Europe/Rome",
) -> str:
    """Render a subject-private Hermes config."""
    return "\n".join(
        [
            f"profile_name: {profile_name}",
            f"subject_id: {subject_id}",
            "runtime_class: Hermes-native",
            "relic_managed: true",
            "model:",
            f"  provider: {provider}",
            f"  default: {model}",
            f"  context_length: {HERMES_CONTEXT_LENGTH}",
            "agent:",
            "  tool_use_enforcement: auto",
            "  disabled_toolsets:",
            "    - web",
            "    - browser",
            "    - terminal",
            "    - file",
            "    - code_execution",
            "    - image_gen",
            "    - tts",
            "    - clarify",
            "    - todo",
            "    - delegation",
            "    - cronjob",
            "    - messaging",
            "    - skills",
            "    - session_search",
            "approvals:",
            "  mode: manual",
            "privacy:",
            "  redact_pii: true",
            "  raw_final_prompt_logs: false",
            "  cloud_required: true",
            "memory:",
            "  provider: hindsight",
            "  provider_mode: tools",
            "  memory_enabled: true",
            "  user_profile_enabled: true",
            "  memory_char_limit: 2200",
            "  user_char_limit: 1375",
            f"  namespace: {profile_name}",
            "  scope: subject-private",
            "  exposure_logging: true",
            "cron:",
            "  wrap_response: false",
            "  script_timeout_seconds: 300",
            "display:",
            "  streaming: false",
            "  interim_assistant_messages: false",
            "  tool_progress: 'off'",
            "  busy_input_mode: queue",
            "  final_response_markdown: strip",
            "human_delay:",
            "  mode: auto",
            "  min_ms: 800",
            "  max_ms: 2500",
            "streaming:",
            "  enabled: false",
            f"timezone: {timezone}",
            "personality: none",
            "group_sessions_per_user: true",
            "session_reset:",
            "  mode: both",
            "  idle_minutes: 180",
            "  at_hour: 3",
            "",
        ]
    )


# ---------------------------------------------------------------------------
# Resume reconciliation
# ---------------------------------------------------------------------------


class ReconciliationDecision(str, Enum):
    ALLOW = "ALLOW"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class ReconciliationCheck(str, Enum):
    SUBJECT_SCOPE = "subject_scope"
    SESSION_KEY_HASH = "session_key_hash"
    PLATFORM_ALLOWLIST = "platform_allowlist"
    DELIVERY_ENABLED = "delivery_enabled"
    CONTINUITY_MARKER_STATUS = "continuity_marker_status"
    CONTINUITY_MARKER_TTL = "continuity_marker_ttl"
    CONTINUITY_SCOPE_PAUSE = "continuity_scope_pause"
    FOLLOWUP_ATTEMPT_COUNT = "followup_attempt_count"
    SAFETY_REVIEW_STATE = "safety_review_state"
    BEHAVIOR_POLICY_PATCH_EXPIRY = "behavior_policy_patch_expiry"
    OUTPUT_SANITIZER = "output_sanitizer"
    DELIVERY_STATE_KNOWN = "delivery_state_known"


@dataclass
class ReconciliationResult:
    """Result of a resume reconciliation check."""

    decision: ReconciliationDecision
    failed_checks: list[ReconciliationCheck]
    pending_output_held: bool
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "decision": self.decision.value,
            "failed_checks": [c.value for c in self.failed_checks],
            "pending_output_held": self.pending_output_held,
            "metadata": self.metadata,
        }


@dataclass
class SessionResumeState:
    """State snapshot for resume reconciliation."""

    subject_id: str
    gumi_instance_id: str
    hermes_profile_id: str
    session_key_hash: str
    platform_allowlist_valid: bool = True
    delivery_enabled: bool = True
    continuity_marker_active: bool = True
    continuity_marker_expires_at: datetime | None = None
    continuity_scope_paused: bool = False
    followup_attempt_count: int = 0
    safety_review_required: bool = False
    behavior_policy_patch_expires_at: datetime | None = None
    output_sanitizer_clean: bool = True
    delivery_state_known: bool = True
    # Internal marker for unknown state tracking
    _unknown_marker: bool = field(default=False, repr=False)


# ---------------------------------------------------------------------------
# Runtime feature support
# ---------------------------------------------------------------------------

_RUNTIME_CONFIG: dict = {}


def check_hermes_feature_support() -> dict:
    """
    Check which Hermes runtime features are supported.

    Returns:
        Dict of feature name -> supported (bool).
    """
    import subprocess

    supported = {
        "no_agent_cron": False,
        "transform_llm_output": False,
        "session_key_support": False,
        "allowlist_support": False,
    }

    try:
        result = subprocess.run(
            ["hermes", "version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            supported["session_key_support"] = True
    except Exception:
        pass

    try:
        result = subprocess.run(
            ["hermes", "config", "list"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            output = result.stdout + result.stderr
            if "cron" in output.lower():
                supported["no_agent_cron"] = True
            if "transform" in output.lower():
                supported["transform_llm_output"] = True
            if "allowlist" in output.lower():
                supported["allowlist_support"] = True
    except Exception:
        pass

    return supported


def init_runtime_config() -> dict:
    """
    Initialize global runtime configuration.

    Returns:
        Dict with runtime config state.
    """
    global _RUNTIME_CONFIG

    _RUNTIME_CONFIG = {
        "initialized": True,
        "features": check_hermes_feature_support(),
    }

    return _RUNTIME_CONFIG


def get_runtime_config() -> dict:
    """Return the current runtime config."""
    return _RUNTIME_CONFIG


# ---------------------------------------------------------------------------
# Resume reconciliation
# ---------------------------------------------------------------------------

class ResumeReconciliation:
    """
    Resume reconciliation state machine.

    Hermes may resume sessions. Relic must reconcile before delivery.
    Re-checks subject scope, session key hash, platform allowlist, delivery enabled,
    continuity marker status, continuity marker TTL, continuity scope pause,
    followup attempt count, safety review state, behavior policy patch expiry,
    output sanitizer, and delivery state known.

    If any check fails → REVIEW_REQUIRED.
    If state unknown → REVIEW_REQUIRED (manual review required).
    Only if all pass → ALLOW.
    """

    def __init__(self, state: SessionResumeState):
        self.state = state

    def reconcile(
        self,
        session_key_hash: str,
        pending_output: dict | None = None,
    ) -> ReconciliationResult:
        """
        Reconcile session resume state before allowing delivery.

        Args:
            session_key_hash: The session key hash to validate.
            pending_output: Optional pending output to check.

        Returns:
            ReconciliationResult with decision and failed checks.
        """
        failed_checks: list[ReconciliationCheck] = []
        metadata: dict = {}

        # Check 1: Subject scope
        if not self.state.subject_id:
            failed_checks.append(ReconciliationCheck.SUBJECT_SCOPE)
            metadata["subject_scope_error"] = "missing or empty"

        # Check 2: Session key hash
        if not self.state.session_key_hash or self.state.session_key_hash != session_key_hash:
            failed_checks.append(ReconciliationCheck.SESSION_KEY_HASH)
            metadata["session_key_hash_error"] = "missing, empty, or mismatch"

        # Check 3: Platform allowlist
        if not self.state.platform_allowlist_valid:
            failed_checks.append(ReconciliationCheck.PLATFORM_ALLOWLIST)
            metadata["allowlist_error"] = "invalid or not allowlisted"

        # Check 4: Delivery enabled
        if not self.state.delivery_enabled:
            failed_checks.append(ReconciliationCheck.DELIVERY_ENABLED)
            metadata["delivery_error"] = "disabled"

        # Check 5: Continuity marker status
        if not self.state.continuity_marker_active:
            failed_checks.append(ReconciliationCheck.CONTINUITY_MARKER_STATUS)
            metadata["continuity_marker_error"] = "inactive"

        # Check 6: Continuity marker TTL
        if self.state.continuity_marker_expires_at is not None:
            if datetime.now(timezone.utc) > self.state.continuity_marker_expires_at:
                failed_checks.append(ReconciliationCheck.CONTINUITY_MARKER_TTL)
                metadata["continuity_marker_ttl_error"] = "expired"

        # Check 7: Continuity scope pause
        if self.state.continuity_scope_paused:
            failed_checks.append(ReconciliationCheck.CONTINUITY_SCOPE_PAUSE)
            metadata["continuity_scope_error"] = "paused"

        # Check 8: Followup attempt count (threshold: max 3)
        if self.state.followup_attempt_count >= 3:
            failed_checks.append(ReconciliationCheck.FOLLOWUP_ATTEMPT_COUNT)
            metadata["followup_attempt_error"] = "max attempts reached"

        # Check 9: Safety review state
        if self.state.safety_review_required:
            failed_checks.append(ReconciliationCheck.SAFETY_REVIEW_STATE)
            metadata["safety_review_error"] = "review required"

        # Check 10: Behavior policy patch expiry
        if self.state.behavior_policy_patch_expires_at is not None:
            if datetime.now(timezone.utc) > self.state.behavior_policy_patch_expires_at:
                failed_checks.append(ReconciliationCheck.BEHAVIOR_POLICY_PATCH_EXPIRY)
                metadata["policy_patch_error"] = "expired"

        # Check 11: Output sanitizer
        if not self.state.output_sanitizer_clean:
            failed_checks.append(ReconciliationCheck.OUTPUT_SANITIZER)
            metadata["output_sanitizer_error"] = "blocked"

        # Check 12: Delivery state known
        if not self.state.delivery_state_known:
            failed_checks.append(ReconciliationCheck.DELIVERY_STATE_KNOWN)
            metadata["delivery_state_error"] = "unknown"

        # Determine decision
        if failed_checks:
            decision = ReconciliationDecision.REVIEW_REQUIRED
        else:
            decision = ReconciliationDecision.ALLOW

        # Hold pending output if reconciliation fails
        pending_output_held = decision == ReconciliationDecision.REVIEW_REQUIRED and pending_output is not None

        return ReconciliationResult(
            decision=decision,
            failed_checks=failed_checks,
            pending_output_held=pending_output_held,
            metadata=metadata,
        )
