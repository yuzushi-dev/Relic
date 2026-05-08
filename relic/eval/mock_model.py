"""Mock LLM model for evaluation harness.

This module provides a mock model that simulates LLM responses
without requiring external API access. All responses are deterministic
and redacted to avoid privacy leakage.
"""

import hashlib
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MockResponse:
    """Mock LLM response."""

    content: str
    model: str = "mock-model-v1"
    tokens_used: int = 0
    latency_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "model": self.model,
            "tokens_used": self.tokens_used,
            "latency_ms": self.latency_ms,
            "metadata": self.metadata,
        }


class MockModel:
    """Mock LLM model for evaluation.

    Simulates different baseline configurations (A0-A5) with
    deterministic, redacted responses for testing purposes.
    """

    BASELINES = ["a0", "a1", "a2", "a3", "a4", "a5"]

    def __init__(self, baseline: str = "a5"):
        if baseline not in self.BASELINES:
            raise ValueError(f"Unknown baseline: {baseline}. Must be one of {self.BASELINES}")
        self.baseline = baseline
        self.model_name = f"mock-{baseline}-v1"
        self._response_cache: dict[str, MockResponse] = {}

    def generate(self, prompt: str, **kwargs) -> MockResponse:
        """Generate a mock response for the given prompt.

        Uses deterministic hashing to ensure reproducible results.
        """
        cache_key = self._make_cache_key(prompt, kwargs)

        if cache_key in self._response_cache:
            return self._response_cache[cache_key]

        # Generate deterministic response based on baseline and prompt
        response = self._generate_response(prompt, **kwargs)

        # Cache the response
        self._response_cache[cache_key] = response

        return response

    def _make_cache_key(self, prompt: str, kwargs: dict) -> str:
        """Create a deterministic cache key."""
        key_parts = [prompt, self.baseline]
        for k, v in sorted(kwargs.items()):
            key_parts.append(f"{k}={v}")
        return hashlib.sha256("|".join(key_parts).encode()).hexdigest()

    def _generate_response(self, prompt: str, **kwargs) -> MockResponse:
        """Generate a baseline-specific response."""
        import time

        start = time.perf_counter()

        # Different baselines have different behaviors
        baseline_responses = {
            "a0": self._generate_a0_response(prompt),
            "a1": self._generate_a1_response(prompt),
            "a2": self._generate_a2_response(prompt),
            "a3": self._generate_a3_response(prompt),
            "a4": self._generate_a4_response(prompt),
            "a5": self._generate_a5_response(prompt),
        }

        content = baseline_responses.get(self.baseline, baseline_responses["a5"])
        latency = (time.perf_counter() - start) * 1000

        return MockResponse(
            content=content,
            model=self.model_name,
            tokens_used=len(content.split()),
            latency_ms=latency,
            metadata={"baseline": self.baseline},
        )

    def _generate_a0_response(self, prompt: str) -> str:
        """A0: No memory, no correction - stateless baseline."""
        return "[A0] No memory available. Context reset. Response: Stateless acknowledgment."

    def _generate_a1_response(self, prompt: str) -> str:
        """A1: No memory capability."""
        return "[A1] No memory capability. Treating as new conversation. Response: Fresh start."

    def _generate_a2_response(self, prompt: str) -> str:
        """A2: Basic memory without correction."""
        if "remember" in prompt.lower():
            return "[A2] I recall this from earlier. Basic memory recall."
        return "[A2] Basic memory response without correction support."

    def _generate_a3_response(self, prompt: str) -> str:
        """A3: Correction only."""
        if "correct" in prompt.lower():
            return "[A3] Correction acknowledged. Previous statement revised."
        return "[A3] Correction-aware response. Ready to acknowledge corrections."

    def _generate_a4_response(self, prompt: str) -> str:
        """A4: Partial memory + correction."""
        has_memory = "remember" in prompt.lower()
        has_correction = "correct" in prompt.lower()

        if has_memory and has_correction:
            return "[A4] Memory with correction. Updated record reflects new facts."
        elif has_memory:
            return "[A4] Partial memory recall with acknowledgment."
        elif has_correction:
            return "[A4] Correction applied with partial memory context."
        return "[A4] Partial memory+correction system."

    def _generate_a5_response(self, prompt: str) -> str:
        """A5: Full memory + correction - target system."""
        has_memory = "remember" in prompt.lower()
        has_correction = "correct" in prompt.lower()
        has_update = "update" in prompt.lower()

        if has_update:
            return "[A5] Memory updated successfully. New context incorporated."
        elif has_memory and has_correction:
            return "[A5] Full memory with correction. Precise recall with updated facts."
        elif has_memory:
            return "[A5] Full memory recall. Accurate context-aware response."
        elif has_correction:
            return "[A5] Correction obeyed. Memory corrected with acknowledgment."
        return "[A5] Full memory+correction system. Complete context awareness."

    def clear_cache(self) -> None:
        """Clear the response cache."""
        self._response_cache.clear()

    def get_baseline(self) -> str:
        """Get current baseline identifier."""
        return self.baseline


def create_mock_model(baseline: str = "a5") -> MockModel:
    """Factory function to create a mock model."""
    return MockModel(baseline=baseline)
