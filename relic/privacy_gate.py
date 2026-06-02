"""Final output privacy gate with rehydration protection.

This module implements the privacy gate that must run before:
- Displaying output to users
- Persisting output to storage
- Handing output to tools

The gate also protects against rehydration attacks where
malicious content could be reintroduced after draft scan.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from enum import Enum

try:
    import structlog
    logger = structlog.get_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)

from relic.persistence import MemoryPersistence, PrivacyLevel, PrivacyTrace


class ScanStage(Enum):
    """Privacy scan stages that must be logged."""
    INPUT_PROMPT_ASSEMBLY = "stage_1_input_prompt_assembly"
    ASSISTANT_DRAFT = "stage_2_assistant_draft"
    REHYDRATION = "stage_3_rehydration"
    FINAL_OUTPUT = "stage_4_final_output"


@dataclass
class PrivacyPolicy:
    """Privacy policy configuration for the gate."""
    restricted_categories: set[str] = field(default_factory=set)
    quarantine_on_s1: bool = True
    warn_on_s2: bool = True
    block_on_s0: bool = True

    @classmethod
    def default(cls) -> PrivacyPolicy:
        """Create default privacy policy."""
        return cls(
            restricted_categories={
                "pii_email",
                "pii_phone",
                "pii_ssn",
                "pii_credit_card",
                "api_key",
                "password",
                "private_key",
            }
        )


class FinalOutputPrivacyGate:
    """Privacy gate for final output before display/persistence.

    This gate implements the zero-knowledge privacy guarantees:
    - Raw final prompt is never persisted
    - Rehydration cannot reintroduce restricted content
    - S0 violations are blocked, S1 quarantined, S2 warned
    """

    def __init__(self, policy: PrivacyPolicy | None = None, persistence: MemoryPersistence | None = None):
        self._policy = policy or PrivacyPolicy.default()
        self._persistence = persistence or MemoryPersistence()
        self._draft_hashes: set[str] = set()  # Track scanned drafts (truncated hashes)

    def scan_input(self, prompt: str, assistant_draft: str) -> PrivacyTrace:
        """Scan input prompt assembly and assistant draft.

        This is stage 1 and 2 - runs before any processing.
        Returns trace for audit purposes.
        """
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
        draft_hash = hashlib.sha256(assistant_draft.encode()).hexdigest()

        # Store truncated draft hash for later verification (matches trace_id)
        draft_hash_short = draft_hash[:16]
        self._draft_hashes.add(draft_hash_short)

        # Check for restricted content
        level = self._classify_content(assistant_draft)

        trace = PrivacyTrace(
            trace_id=draft_hash_short,
            stage=ScanStage.INPUT_PROMPT_ASSEMBLY.value,
            content_hash=prompt_hash,
            privacy_level=level,
            policy_applied=self._get_policy_action(level),
            rehydration_context={"draft_hash": draft_hash_short},
        )

        # Log to trace
        self._persistence.append_trace_direct(trace)

        return trace

    def scan_rehydration(self, rehydrated_content: str, original_draft_hash: str) -> tuple[PrivacyLevel, PrivacyTrace]:
        """Scan content after rehydration to prevent malicious injection.

        Must verify the rehydrated content matches scanned draft
        and has not been tampered with.
        """
        # Normalize to truncated hash for lookup
        draft_hash_key = original_draft_hash[:16] if len(original_draft_hash) > 16 else original_draft_hash

        if draft_hash_key not in self._draft_hashes:
            # Unknown draft - this is suspicious
            level = PrivacyLevel.S0_HARD_VIOLATION
            policy_action = "block_unknown_rehydration"
        else:
            # Check for restricted content patterns
            level = self._classify_content(rehydrated_content)
            policy_action = self._get_policy_action(level)

        trace = PrivacyTrace(
            trace_id=f"rehyd_{original_draft_hash[:8]}",
            stage=ScanStage.REHYDRATION.value,
            content_hash=hashlib.sha256(rehydrated_content.encode()).hexdigest(),
            privacy_level=level,
            policy_applied=policy_action,
            rehydration_context={"original_draft_hash": original_draft_hash},
        )

        self._persistence.append_trace_direct(trace)

        return level, trace

    def scan_final_output(self, output: str, original_draft_hash: str) -> tuple[bool, PrivacyTrace]:
        """Scan final output before display/persistence.

        This is the critical stage 4 gate - must run before:
        - Displaying to user
        - Persisting to storage
        - Handing to tools

        Returns (allowed, trace) tuple.
        """
        # Normalize to truncated hash for lookup
        draft_hash_key = original_draft_hash[:16] if len(original_draft_hash) > 16 else original_draft_hash

        if draft_hash_key not in self._draft_hashes:
            # Block unknown content at final gate
            level = PrivacyLevel.S0_HARD_VIOLATION
            policy_action = "block_unknown_final_output"
            allowed = False
        else:
            level, _ = self.scan_rehydration(output, original_draft_hash)
            policy_action = self._get_policy_action(level)

            # S0 blocked, S1 quarantined (zero runtime influence), S2 warned
            if level == PrivacyLevel.S0_HARD_VIOLATION:
                allowed = False
            elif level == PrivacyLevel.S1_QUARANTINE:
                allowed = False  # Zero runtime influence
            else:
                allowed = True

        trace = PrivacyTrace(
            trace_id=f"final_{original_draft_hash[:8]}",
            stage=ScanStage.FINAL_OUTPUT.value,
            content_hash=hashlib.sha256(output.encode()).hexdigest(),
            privacy_level=level,
            policy_applied=policy_action,
        )

        self._persistence.append_trace_direct(trace)

        return allowed, trace

    def _classify_content(self, content: str) -> PrivacyLevel:
        """Classify content privacy level based on policy.

        Returns:
            S0: Hard violation - blocked
            S1: Quarantine - zero runtime influence
            S2: Warning - reported but allowed
            SAFE: No issues detected
        """
        restricted = self._policy.restricted_categories

        # Check for PII patterns
        pii_patterns = {
            "pii_email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            "pii_phone": r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
            "pii_ssn": r'\b\d{3}-\d{2}-\d{4}\b',
            "pii_credit_card": r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',
        }

        api_key_patterns = {
            "api_key": r'(?i)(api[_-]?key|apikey)\s*[:=]\s*["\']?[A-Za-z0-9_-]{16,}["\']?',
            "password": r'(?i)(password|passwd|pwd)\s*[:=]\s*["\']?[^\s"\']{8,}["\']?',
            "private_key": r'-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----',
        }

        # Check PII patterns
        for category, pattern in pii_patterns.items():
            if category in restricted and re.search(pattern, content):
                return PrivacyLevel.S0_HARD_VIOLATION

        # Check API key patterns
        for category, pattern in api_key_patterns.items():
            if category in restricted and re.search(pattern, content):
                return PrivacyLevel.S0_HARD_VIOLATION

        # Check for overpersonalization (S2 warning)
        # Simple heuristic: excessive first-person pronouns in context
        first_person_count = len(re.findall(r'\b(I|me|my|mine|myself|we|us|our|ours)\b', content, re.IGNORECASE))
        word_count = len(content.split())

        if word_count > 10 and first_person_count / word_count > 0.3:
            return PrivacyLevel.S2_WARNING

        return PrivacyLevel.SAFE

    def _get_policy_action(self, level: PrivacyLevel) -> str:
        """Get policy action string for a privacy level."""
        if level == PrivacyLevel.S0_HARD_VIOLATION:
            return "block_s0_violation"
        elif level == PrivacyLevel.S1_QUARANTINE:
            return "quarantine_s1_content"
        elif level == PrivacyLevel.S2_WARNING:
            return "warn_s2_overpersonalization"
        return "allow_safe_content"

    def is_allowed(self, level: PrivacyLevel) -> bool:
        """Check if a privacy level is allowed for runtime use."""
        if level == PrivacyLevel.S0_HARD_VIOLATION:
            return False
        if level == PrivacyLevel.S1_QUARANTINE:
            return False  # Zero runtime influence
        return True

    def get_trace(self) -> list[PrivacyTrace]:
        """Get all privacy traces."""
        return self._persistence.get_trace()

    def clear(self) -> None:
        """Clear state (for testing)."""
        self._draft_hashes.clear()
        self._persistence.clear_trace()


class PrivacyGate:
    """Output privacy gate, blocks workflow/sensitive content from SOUL.md and other restricted sources."""

    _BLOCKED_SOURCES = {"SOUL.md"}
    _BLOCKED_CONTENT_TYPES = {"workflow"}

    def filter_output(self, block: dict) -> dict:
        source = block.get("source", "")
        content_type = block.get("content_type", "")
        if source in self._BLOCKED_SOURCES and content_type in self._BLOCKED_CONTENT_TYPES:
            return {**block, "blocked": True, "content": ""}
        return block



# Monkey-patch PrivacyGate.filter_output to add PII redaction
import re as _re
_PII_PATTERNS = [
    _re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    _re.compile(r"\b\d{1,5}\s+\w[\w\s]+(?:St|Ave|Rd|Blvd|Dr|Ln|Way|Ct)\b"),
    _re.compile(r"\b[\w.+-]+@[\w-]+\.\w+\b"),
]

def _pii_filter_output(self, block: dict) -> dict:
    source = block.get("source", "")
    content_type = block.get("content_type", "")
    if source in self._BLOCKED_SOURCES and content_type in self._BLOCKED_CONTENT_TYPES:
        return {**block, "blocked": True, "content": ""}
    content = block.get("content", "")
    if content:
        for p in _PII_PATTERNS:
            content = p.sub("[REDACTED]", content)
        return {**block, "content": content, "redacted": True}
    return block

PrivacyGate.filter_output = _pii_filter_output
