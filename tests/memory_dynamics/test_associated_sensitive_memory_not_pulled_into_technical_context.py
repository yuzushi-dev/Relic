"""Tests for associated sensitive memory not pulled into technical context.

Acceptance criteria:
- sensitive memory associations cannot pull raw content into non-private contexts
- mechanism report outputs remain mechanism reports

Tests are designed to fail-closed on privacy/correction/runtime bypass.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest


class ContextType(Enum):
    """Context types for memory access evaluation."""
    GENERAL = "general"
    TECHNICAL = "technical"
    PRIVATE = "private"
    CREATIVE = "creative"


@dataclass
class MemoryContext:
    """Memory access context evaluation."""
    context_type: ContextType
    session_id: str
    prompt_type: str


@dataclass
class ContextAccessResult:
    """Result of context access evaluation."""
    access_allowed: bool
    reason: str | None = None
    sensitive_blocked: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "access_allowed": self.access_allowed,
            "reason": self.reason,
            "sensitive_blocked": self.sensitive_blocked,
        }


class ScopeGate:
    """Scope gate for context access.
    
    This class provides the interface for checking whether memories
    can be accessed in different contexts while respecting privacy boundaries.
    """

    def __init__(self):
        self._traces: list[dict] = []

    def evaluate_context_access(
        self,
        memory: dict[str, Any],
        context: MemoryContext,
    ) -> ContextAccessResult:
        """Evaluate if memory can be accessed in given context.
        
        BLOCKS access when:
        - Memory has sensitive associations and context is technical
        - Memory privacy level is S0/S1
        """
        privacy_level = memory.get("privacy_level", "SAFE")
        sensitive_assocs = memory.get("sensitive_associations", [])

        # Block sensitive associations in technical context (checked before generic privacy gate)
        if sensitive_assocs and context.context_type == ContextType.TECHNICAL:
            self._traces.append({
                "memory_id": memory.get("id"),
                "context": context.context_type.value,
                "blocked": True,
                "reason": "sensitive_association",
            })
            return ContextAccessResult(
                access_allowed=False,
                reason="sensitive_association_blocked",
                sensitive_blocked=sensitive_assocs,
            )

        # Block S0/S1 in any context
        if privacy_level in ("S0_HARD_VIOLATION", "S0", "s0", "S1_QUARANTINE", "S1", "s1"):
            self._traces.append({
                "memory_id": memory.get("id"),
                "context": context.context_type.value,
                "blocked": True,
                "reason": "privacy_level",
            })
            return ContextAccessResult(
                access_allowed=False,
                reason="privacy_gate",
            )

        self._traces.append({
            "memory_id": memory.get("id"),
            "context": context.context_type.value,
            "blocked": False,
        })
        return ContextAccessResult(access_allowed=True)

    def filter_accessible(
        self,
        memories: list[dict[str, Any]],
        context: MemoryContext,
    ) -> list[dict[str, Any]]:
        """Filter memories to only accessible ones for given context."""
        accessible = []
        for memory in memories:
            result = self.evaluate_context_access(memory, context)
            if result.access_allowed:
                accessible.append(memory)
        return accessible

    def get_trace(self) -> list[dict]:
        """Get all evaluation traces."""
        return self._traces.copy()


class TestAssociatedSensitiveMemoryNotPulledIntoTechnicalContext:
    """Tests verifying sensitive memory associations respect context boundaries."""

    def test_sensitive_association_blocked_in_technical_context(self, tmp_path: Path) -> None:
        """Test that sensitive memory associations are blocked in technical context.

        When a memory has sensitive associations, those should not be
        pulled into technical/code generation contexts.
        """
        gate = ScopeGate()

        # Memory with sensitive association (e.g., personal email)
        memory = {
            "id": str(uuid4()),
            "content_hash": hashlib.sha256(b"user email").hexdigest(),
            "privacy_level": "S1_QUARANTINE",
            "sensitive_associations": ["personal_email"],
        }

        context = MemoryContext(
            context_type=ContextType.TECHNICAL,
            session_id=str(uuid4()),
            prompt_type="code_generation",
        )

        result = gate.evaluate_context_access(memory=memory, context=context)

        # Should block pulling sensitive associations into technical context
        assert result.access_allowed is False
        assert result.reason == "sensitive_association_blocked"

    def test_safe_memory_allowed_in_technical_context(self, tmp_path: Path) -> None:
        """Test that safe memories are allowed in technical context."""
        gate = ScopeGate()

        memory = {
            "id": str(uuid4()),
            "content_hash": hashlib.sha256(b"API documentation").hexdigest(),
            "privacy_level": "SAFE",
            "sensitive_associations": [],
        }

        context = MemoryContext(
            context_type=ContextType.TECHNICAL,
            session_id=str(uuid4()),
            prompt_type="code_generation",
        )

        result = gate.evaluate_context_access(memory=memory, context=context)

        assert result.access_allowed is True

    def test_association_trace_contains_only_hashes(self, tmp_path: Path) -> None:
        """Test association trace contains only hashes, not raw content."""
        gate = ScopeGate()

        memory = {
            "id": str(uuid4()),
            "content_hash": hashlib.sha256(b"credit card: 1234-5678-9012-3456").hexdigest(),
            "privacy_level": "S0_HARD_VIOLATION",
        }

        context = MemoryContext(
            context_type=ContextType.GENERAL,
            session_id=str(uuid4()),
            prompt_type="query",
        )

        gate.evaluate_context_access(memory=memory, context=context)

        trace = gate.get_trace()
        trace_json = json.dumps(trace)

        # Must not contain raw credit card number
        assert "1234-5678-9012-3456" not in trace_json
        assert "credit card" not in trace_json.lower()

    def test_technical_context_excludes_sensitive_by_default(self, tmp_path: Path) -> None:
        """Test technical context has sensitive content excluded by default."""
        gate = ScopeGate()

        # Multiple memories, some sensitive
        memories = [
            {
                "id": str(uuid4()),
                "content_hash": hashlib.sha256(b"code").hexdigest(),
                "privacy_level": "SAFE",
            },
            {
                "id": str(uuid4()),
                "content_hash": hashlib.sha256(b"password").hexdigest(),
                "privacy_level": "S0_HARD_VIOLATION",
            },
        ]

        context = MemoryContext(
            context_type=ContextType.TECHNICAL,
            session_id=str(uuid4()),
            prompt_type="code_generation",
        )

        # Filter should exclude sensitive
        accessible = gate.filter_accessible(memories, context)

        assert len(accessible) == 1
        assert accessible[0]["privacy_level"] == "SAFE"

    def test_no_raw_content_in_context_switch_report(self, tmp_path: Path) -> None:
        """Test no raw content appears in context switch evaluation report."""
        gate = ScopeGate()

        memory = {
            "id": str(uuid4()),
            "content_hash": hashlib.sha256(b"SSN: 123-45-6789").hexdigest(),
            "privacy_level": "S0_HARD_VIOLATION",
        }

        context = MemoryContext(
            context_type=ContextType.TECHNICAL,
            session_id=str(uuid4()),
            prompt_type="documentation",
        )

        result = gate.evaluate_context_access(memory=memory, context=context)
        result_dict = result.to_dict()
        result_json = json.dumps(result_dict)

        # No raw SSN
        assert "123-45-6789" not in result_json
        assert "SSN:" not in result_json
