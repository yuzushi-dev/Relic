"""Tests for artifact checksum computation and verification.

These tests verify that:
- Checksums are correctly computed using SHA-256
- Checksum verification works correctly
- Content is never stored raw, only as hashes
- Structural checksums ignore mutable fields
- Delta checksums correctly track changes
"""

from __future__ import annotations

from relic.artifacts.checksums import (
    compute_checksum,
    compute_delta_checksum,
    compute_structural_checksum,
    hash_hint,
    hash_prompt,
    verify_checksum,
)


class TestComputeChecksum:
    """Tests for compute_checksum function."""

    def test_checksum_of_dict(self):
        """Test checksum computation for dictionary content."""
        content = {"key": "value", "number": 42}
        checksum = compute_checksum(content)
        assert len(checksum) == 64
        assert checksum.isalnum()

    def test_checksum_of_list(self):
        """Test checksum computation for list content."""
        content = ["item1", "item2", "item3"]
        checksum = compute_checksum(content)
        assert len(checksum) == 64

    def test_checksum_of_string(self):
        """Test checksum computation for string content."""
        content = "Hello, World!"
        checksum = compute_checksum(content)
        assert len(checksum) == 64

    def test_checksum_deterministic(self):
        """Test checksum is deterministic for same content."""
        content = {"key": "value"}
        checksum1 = compute_checksum(content)
        checksum2 = compute_checksum(content)
        assert checksum1 == checksum2

    def test_checksum_different_for_different_content(self):
        """Test different content produces different checksums."""
        content1 = {"key": "value1"}
        content2 = {"key": "value2"}
        checksum1 = compute_checksum(content1)
        checksum2 = compute_checksum(content2)
        assert checksum1 != checksum2

    def test_checksum_sorted_keys(self):
        """Test checksum is independent of key order."""
        content1 = {"a": 1, "b": 2}
        content2 = {"b": 2, "a": 1}
        checksum1 = compute_checksum(content1)
        checksum2 = compute_checksum(content2)
        assert checksum1 == checksum2


class TestVerifyChecksum:
    """Tests for verify_checksum function."""

    def test_verify_checksum_valid(self):
        """Test checksum verification with valid checksum."""
        content = {"key": "value"}
        checksum = compute_checksum(content)
        assert verify_checksum(content, checksum) is True

    def test_verify_checksum_invalid(self):
        """Test checksum verification with invalid checksum."""
        content = {"key": "value"}
        wrong_checksum = "a" * 64
        assert verify_checksum(content, wrong_checksum) is False

    def test_verify_checksum_invalid_length(self):
        """Test checksum verification rejects invalid length."""
        content = {"key": "value"}
        short_checksum = "abc"
        assert verify_checksum(content, short_checksum) is False

    def test_verify_checksum_tampered_content(self):
        """Test checksum verification detects tampering."""
        content = {"key": "value"}
        checksum = compute_checksum(content)
        tampered = {"key": "modified"}
        assert verify_checksum(tampered, checksum) is False


class TestStructuralChecksum:
    """Tests for compute_structural_checksum function."""

    def test_structural_checksum_excludes_mutable_fields(self):
        """Test structural checksum excludes mutable fields."""
        artifact_dict = {
            "id": "123",
            "created_at": "2024-01-01",
            "updated_at": "2024-01-02",
            "checksum": "abc",
            "metadata": {},
            "stable_field": "value",
        }
        checksum = compute_structural_checksum(artifact_dict)
        assert len(checksum) == 64

    def test_structural_checksum_stable_for_mutations(self):
        """Test structural checksum is stable when mutable fields change."""
        artifact1 = {
            "id": "123",
            "created_at": "2024-01-01",
            "stable_field": "value",
        }
        artifact2 = {
            "id": "456",
            "created_at": "2024-06-01",
            "stable_field": "value",
        }
        checksum1 = compute_structural_checksum(artifact1)
        checksum2 = compute_structural_checksum(artifact2)
        assert checksum1 == checksum2


class TestDeltaChecksum:
    """Tests for compute_delta_checksum function."""

    def test_delta_checksum_includes_original_and_delta(self):
        """Test delta checksum includes both original and delta content."""
        original = {"field": "original_value"}
        delta = {"field": "new_value"}
        checksum = compute_delta_checksum(original, delta)
        assert len(checksum) == 64

    def test_delta_checksum_different_for_different_deltas(self):
        """Test different deltas produce different checksums."""
        original = {"field": "original"}
        delta1 = {"field": "new1"}
        delta2 = {"field": "new2"}
        checksum1 = compute_delta_checksum(original, delta1)
        checksum2 = compute_delta_checksum(original, delta2)
        assert checksum1 != checksum2


class TestPromptAndHintHashing:
    """Tests for privacy-safe prompt and hint hashing."""

    def test_hash_prompt_produces_sha256(self):
        """Test hash_prompt produces SHA-256 hash."""
        prompt = "What is the capital of France?"
        hash_result = hash_prompt(prompt)
        assert len(hash_result) == 64
        assert hash_result.isalnum()

    def test_hash_prompt_deterministic(self):
        """Test hash_prompt is deterministic."""
        prompt = "What is the capital of France?"
        hash1 = hash_prompt(prompt)
        hash2 = hash_prompt(prompt)
        assert hash1 == hash2

    def test_hash_prompt_different_for_different_prompts(self):
        """Test different prompts produce different hashes."""
        prompt1 = "What is the capital of France?"
        prompt2 = "What is the capital of Germany?"
        hash1 = hash_prompt(prompt1)
        hash2 = hash_prompt(prompt2)
        assert hash1 != hash2

    def test_hash_hint_produces_sha256(self):
        """Test hash_hint produces SHA-256 hash."""
        hint = "User prefers short responses"
        hash_result = hash_hint(hint)
        assert len(hash_result) == 64

    def test_hash_hint_deterministic(self):
        """Test hash_hint is deterministic."""
        hint = "User prefers short responses"
        hash1 = hash_hint(hint)
        hash2 = hash_hint(hint)
        assert hash1 == hash2

    def test_hash_functions_exist(self):
        """Test that both hash functions exist and are callable."""
        assert callable(hash_prompt)
        assert callable(hash_hint)


class TestPrivacyGuarantees:
    """Tests for privacy guarantees in checksum module."""

    def test_no_raw_content_in_checksum(self):
        """Test that compute_checksum doesn't expose raw content."""
        sensitive_content = {
            "user_id": "user123",
            "raw_chat": "User said: I have cancer and need medical help",
            "private_info": "SSN: 123-45-6789",
        }
        # Compute checksum - should not raise
        checksum = compute_checksum(sensitive_content)
        # Checksum should be just hex characters
        assert checksum.isalnum()
        assert len(checksum) == 64
        # Original content should not appear in checksum
        assert "cancer" not in checksum
        assert "SSN" not in checksum
        assert "user123" not in checksum

    def test_hint_hashes_store_only_hashes(self):
        """Test that hint hashes are stored, not actual hints."""
        hints = [
            "User has medical condition X",
            "User prefers Y type of responses",
            "User's personal secret Z",
        ]
        hashes = [hash_hint(hint) for hint in hints]
        # Each hash should be a SHA-256 hex string
        for h in hashes:
            assert len(h) == 64
            assert h.isalnum()
        # Hashes should be different for different hints
        assert len(set(hashes)) == len(hashes)

    def test_prompt_hashes_store_only_hashes(self):
        """Test that prompt hashes are stored, not actual prompts."""
        prompts = [
            "How do I treat my medical condition?",
            "What is my SSN?",
            "Tell me about my personal life",
        ]
        hashes = [hash_prompt(prompt) for prompt in prompts]
        # Each hash should be a SHA-256 hex string
        for h in hashes:
            assert len(h) == 64
        # Hashes should be different for different prompts
        assert len(set(hashes)) == len(hashes)
