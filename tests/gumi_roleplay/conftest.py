"""Test fixtures for PromptContextPack tests."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from relic.context_pack import (
    PromptContextPack,
    SystemSource,
    MemoryCandidate,
    KnowledgeCandidate,
    ContinuityItem,
    BlockedItem,
    SubjectScope,
    TaskType,
    RoleplayLevel,
    ContinuityMode,
    DisclosureLevel,
    ContextSource,
)


def _utcnow() -> datetime:
    """Get current UTC datetime."""
    return datetime.now(timezone.utc)


@pytest.fixture
def minimal_pack() -> PromptContextPack:
    """Minimal valid pack for testing."""
    return PromptContextPack(
        schema_version="1.0",
        pack_id="PCP-test-001",
        session_id="SES-123",
        turn_id="TURN-1",
        created_at=_utcnow(),
        task_type=TaskType.FACTUAL,
        roleplay_level=RoleplayLevel.OFF,
        continuity_mode=ContinuityMode.NONE,
        input_hash="sha256:test-minimal-hash",
    )


@pytest.fixture
def full_pack_with_scope() -> PromptContextPack:
    """Full pack with subject scope for disclosure testing."""
    alice_scope = SubjectScope(
        subject_id="alice",
        disclosure_level=DisclosureLevel.STANDARD,
        is_active=True,
    )
    bob_scope = SubjectScope(
        subject_id="bob",
        disclosure_level=DisclosureLevel.RESTRICTED,
        is_active=True,
    )

    return PromptContextPack(
        schema_version="1.0",
        pack_id="PCP-test-full",
        session_id="SES-full",
        turn_id="TURN-full",
        created_at=_utcnow(),
        task_type=TaskType.RELATIONAL,
        roleplay_level=RoleplayLevel.NORMAL,
        continuity_mode=ContinuityMode.COMPACT,
        disclosure_required=True,
        system_sources=[
            SystemSource(
                source=ContextSource.MEMORY,
                priority=80,
                content="Memory context for alice",
                injected=True,
                scope=[alice_scope],
            ),
            SystemSource(
                source=ContextSource.SYSTEM,
                priority=50,
                content="System prompt",
                injected=True,
                scope=[],
            ),
        ],
        continuity_items=[
            ContinuityItem(
                item_id="ci-1",
                item_type="conversation",
                summary="Previous conversation about project",
                position=1,
                scope=[alice_scope, bob_scope],
            ),
        ],
        memory_candidates=[
            MemoryCandidate(
                candidate_id="mc-1",
                memory_type="episodic",
                summary="Alice mentioned she likes cats",
                relevance_score=0.85,
                scope=[alice_scope],
            ),
        ],
        knowledge_candidates=[
            KnowledgeCandidate(
                candidate_id="kc-1",
                knowledge_type="factual",
                content="Cats are mammals",
                confidence=0.95,
                scope=[bob_scope],
            ),
        ],
        blocked_items=[
            BlockedItem(
                item_id="blocked-1",
                reason="Privacy: contains user private facts",
                blocked_at=_utcnow(),
                scope=[SubjectScope(
                    subject_id="sensitive-user",
                    disclosure_level=DisclosureLevel.PRIVATE,
                )],
            ),
        ],
        input_hash="sha256:test-full-hash",
    )


@pytest.fixture
def pack_with_blocked_items() -> PromptContextPack:
    """Pack with multiple blocked items for testing."""
    return PromptContextPack(
        schema_version="1.0",
        pack_id="PCP-blocked-test",
        session_id="SES-blocked",
        turn_id="TURN-blocked",
        created_at=_utcnow(),
        task_type=TaskType.FACTUAL,
        blocked_items=[
            BlockedItem(item_id="blocked-a", reason="Contains PII"),
            BlockedItem(item_id="blocked-b", reason="Contains sensitive data"),
            BlockedItem(item_id="blocked-c", reason="User requested blocking"),
        ],
        input_hash="sha256:test-blocked-hash",
    )


@pytest.fixture
def pack_missing_scope() -> PromptContextPack:
    """Pack missing subject scope - should fail validation."""
    return PromptContextPack(
        schema_version="1.0",
        pack_id="PCP-no-scope",
        session_id="SES-no-scope",
        turn_id="TURN-no-scope",
        created_at=_utcnow(),
        task_type=TaskType.TECHNICAL,
        system_sources=[
            SystemSource(
                source=ContextSource.MEMORY,
                priority=50,
                content="Some memory content",
                injected=True,
                scope=[],  # Empty scope!
            ),
        ],
        input_hash="sha256:test-no-scope-hash",
    )


@pytest.fixture
def pack_with_raw_prompt_marker() -> PromptContextPack:
    """Pack with raw prompt marker - should fail validation."""
    return PromptContextPack(
        schema_version="1.0",
        pack_id="PCP-raw-marker",
        session_id="SES-raw",
        turn_id="TURN-raw",
        created_at=_utcnow(),
        task_type=TaskType.FACTUAL,
        system_sources=[
            SystemSource(
                source=ContextSource.USER,
                priority=50,
                content="[RAW_PROMPT] This is raw user input that should be blocked",
                injected=True,
            ),
        ],
        input_hash="sha256:test-raw-marker-hash",
    )
