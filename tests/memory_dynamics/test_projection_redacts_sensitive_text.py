"""Tests for projection redacts sensitive text.

Acceptance criteria:
- human-readable projections are redacted
- dynamic memory traces contain raw sensitive text
"""

from __future__ import annotations

import json

import pytest

from relic.memory_dynamics import MemoryDynamicsService, ProjectionGenerator


class TestProjectionRedactsSensitiveText:
    """Tests verifying projections redact sensitive text."""

    def test_email_is_redacted(self) -> None:
        """Test that email addresses are redacted."""
        generator = ProjectionGenerator()
        
        content = "Contact me at john.doe@example.com"
        projection = generator.generate_projection(
            memory_id="test-1",
            content=content,
        )
        
        assert "john.doe@example.com" not in projection.redacted_content
        assert "[REDACTED_EMAIL]" in projection.redacted_content

    def test_phone_is_redacted(self) -> None:
        """Test that phone numbers are redacted."""
        generator = ProjectionGenerator()
        
        content = "Call me at 555-123-4567"
        projection = generator.generate_projection(
            memory_id="test-2",
            content=content,
        )
        
        assert "555-123-4567" not in projection.redacted_content
        assert "[REDACTED_PHONE]" in projection.redacted_content

    def test_api_key_is_redacted(self) -> None:
        """Test that API keys are redacted."""
        generator = ProjectionGenerator()
        
        content = "API key: sk_live_abc123xyz456def789"
        projection = generator.generate_projection(
            memory_id="test-3",
            content=content,
        )
        
        assert "sk_live_" not in projection.redacted_content
        assert "[REDACTED_API_KEY]" in projection.redacted_content

    def test_password_is_redacted(self) -> None:
        """Test that passwords are redacted."""
        generator = ProjectionGenerator()
        
        content = "Password: SuperSecret123!"
        projection = generator.generate_projection(
            memory_id="test-4",
            content=content,
        )
        
        assert "SuperSecret123" not in projection.redacted_content
        assert "[REDACTED_PASSWORD]" in projection.redacted_content

    def test_ssn_is_redacted(self) -> None:
        """Test that SSNs are redacted."""
        generator = ProjectionGenerator()
        
        content = "SSN: 123-45-6789"
        projection = generator.generate_projection(
            memory_id="test-5",
            content=content,
        )
        
        assert "123-45-6789" not in projection.redacted_content
        assert "[REDACTED_SSN]" in projection.redacted_content

    def test_multiple_sensitive_patterns_redacted(self) -> None:
        """Test that multiple sensitive patterns are all redacted."""
        generator = ProjectionGenerator()
        
        content = "Email: test@test.com, Phone: 555-123-4567, SSN: 123-45-6789"
        projection = generator.generate_projection(
            memory_id="test-6",
            content=content,
        )
        
        assert "test@test.com" not in projection.redacted_content
        assert "555-123-4567" not in projection.redacted_content
        assert "123-45-6789" not in projection.redacted_content
        
        # Multiple redaction markers present
        assert "[REDACTED_EMAIL]" in projection.redacted_content
        assert "[REDACTED_PHONE]" in projection.redacted_content
        assert "[REDACTED_SSN]" in projection.redacted_content

    def test_redacted_fields_listed(self) -> None:
        """Test that redacted fields are recorded."""
        generator = ProjectionGenerator()
        
        content = "Email: user@example.com and another@test.com"
        projection = generator.generate_projection(
            memory_id="test-7",
            content=content,
        )
        
        assert len(projection.redacted_fields) > 0

    def test_projection_contains_hash_not_raw_content(self) -> None:
        """Test that projection contains hash, not raw content."""
        generator = ProjectionGenerator()
        
        content = "My secret API key is sk_live_abc123xyz"
        projection = generator.generate_projection(
            memory_id="test-8",
            content=content,
        )
        
        # Hash should be stored
        assert projection.content_hash is not None
        # Raw content should not be in redacted output
        assert "sk_live_" not in projection.redacted_content

    def test_service_generates_redacted_projection(self) -> None:
        """Test that service generates redacted projections."""
        service = MemoryDynamicsService()
        
        projection = service.generate_projection(
            memory_id="service-test",
            content="Email: secret@test.com",
            privacy_level="S0",
        )
        
        assert projection["redacted_content"] != "Email: secret@test.com"
        assert "[REDACTED" in projection["redacted_content"]

    def test_verify_no_raw_sensitive(self) -> None:
        """Test verification that output contains no raw sensitive text."""
        generator = ProjectionGenerator()
        
        content = "Normal content without sensitive data"
        projection = generator.generate_projection(
            memory_id="test-9",
            content=content,
        )
        
        is_clean = generator.verify_no_raw_sensitive(projection.redacted_content)
        assert is_clean is True
