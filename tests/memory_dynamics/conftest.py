"""Pytest configuration and fixtures for memory dynamics tests."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest

from relic.persistence import MemoryPersistence


@pytest.fixture
def memory_persistence(tmp_path: Path) -> Generator[MemoryPersistence, None, None]:
    """Provide a MemoryPersistence instance with temporary trace file."""
    persistence = MemoryPersistence(trace_path=tmp_path / "trace.jsonl")
    yield persistence
    persistence.clear_trace()


@pytest.fixture
def safe_content() -> str:
    """Provide safe test content without PII."""
    return "General knowledge: The capital of France is Paris."


@pytest.fixture
def s0_content() -> str:
    """Provide S0 violation test content."""
    return "Secret API key: sk_live_abc123xyz456def789"


@pytest.fixture
def s1_content() -> str:
    """Provide S1 quarantine test content."""
    return "Personal note: User prefers dark mode theme settings"
