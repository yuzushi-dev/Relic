"""Tests for debug bundle module."""

import json

from relic.eval.debug_bundle import (
    DebugBundle,
    PrivacyRedactor,
    create_redacted_entry,
    create_synthetic_entry,
    emit_debug_bundle,
)


class TestPrivacyRedactor:
    """Tests for PrivacyRedactor."""

    def test_no_redaction_needed(self):
        """Test text without private information."""
        redactor = PrivacyRedactor()

        text = "This is a normal text with no private information."
        redacted, placeholder_map = redactor.redact(text)

        assert redacted == text
        assert len(placeholder_map) == 0

    def test_email_redaction(self):
        """Test email redaction."""
        redactor = PrivacyRedactor()

        text = "Contact me at john.doe@example.com for more info."
        redacted, placeholder_map = redactor.redact(text)

        assert "john.doe@example.com" not in redacted
        assert "[REDACTED_EMAIL" in redacted
        assert any("email" in v for v in placeholder_map.values())

    def test_phone_redaction(self):
        """Test phone number redaction."""
        redactor = PrivacyRedactor()

        text = "Call me at 555-123-4567."
        redacted, placeholder_map = redactor.redact(text)

        assert "555-123-4567" not in redacted
        assert "[REDACTED_PHONE" in redacted

    def test_multiple_patterns(self):
        """Test multiple privacy patterns in one text."""
        redactor = PrivacyRedactor()

        text = "Email: test@test.com, Phone: 555-123-4567"
        redacted, placeholder_map = redactor.redact(text)

        assert "[REDACTED_EMAIL" in redacted
        assert "[REDACTED_PHONE" in redacted
        assert len(placeholder_map) >= 2


class TestRedactedEntry:
    """Tests for RedactedEntry dataclass."""

    def test_create_redacted_entry(self):
        """Test creating a redacted entry."""
        entry = create_redacted_entry(
            entry_id="test_1",
            entry_type="prompt",
            content="Test content with sensitive data: test@example.com",
        )

        assert entry.entry_id == "test_1"
        assert entry.entry_type == "prompt"
        assert "[REDACTED_EMAIL" in entry.redacted_content
        assert len(entry.placeholder_map) > 0

    def test_redacted_entry_to_dict(self):
        """Test serializing redacted entry."""
        entry = create_redacted_entry(
            entry_id="test_1",
            entry_type="response",
            content="Test content",
        )

        data = entry.to_dict()
        assert data["entry_id"] == "test_1"
        assert "redacted_content" in data
        assert "placeholder_map" in data


class TestSyntheticEntry:
    """Tests for SyntheticEntry dataclass."""

    def test_create_synthetic_entry(self):
        """Test creating a synthetic entry."""
        entry = create_synthetic_entry(
            entry_id="synth_1",
            entry_type="prompt",
            seed=42,
        )

        assert entry.entry_id == "synth_1"
        assert entry.entry_type == "prompt"
        assert "[SYNTHETIC]" in entry.synthetic_content
        assert entry.generation_seed == 42

    def test_synthetic_entry_deterministic(self):
        """Test synthetic entry generation is deterministic."""
        entry1 = create_synthetic_entry("test", "prompt", seed=123)
        entry2 = create_synthetic_entry("test", "prompt", seed=123)

        assert entry1.synthetic_content == entry2.synthetic_content

    def test_synthetic_entry_different_seeds(self):
        """Test different seeds produce different entries."""
        entry1 = create_synthetic_entry("test", "prompt", seed=123)
        entry2 = create_synthetic_entry("test", "prompt", seed=456)

        assert entry1.synthetic_content != entry2.synthetic_content


class TestDebugBundle:
    """Tests for DebugBundle class."""

    def test_create_empty_bundle(self):
        """Test creating an empty debug bundle."""
        bundle = DebugBundle(
            bundle_id="test_bundle",
            created_at="2024-01-01T00:00:00Z",
        )

        assert bundle.bundle_id == "test_bundle"
        assert len(bundle.redacted_replay) == 0
        assert bundle.synthetic_replay is None

    def test_bundle_to_dict(self):
        """Test serializing bundle."""
        bundle = DebugBundle(
            bundle_id="test_bundle",
            created_at="2024-01-01T00:00:00Z",
            redacted_replay=[
                create_redacted_entry("test_1", "prompt", "Test content"),
            ],
        )

        data = bundle.to_dict()
        assert data["bundle_id"] == "test_bundle"
        assert len(data["redacted_replay"]) == 1

    def test_bundle_to_json(self, tmp_path):
        """Test exporting bundle as JSON."""
        bundle = DebugBundle(
            bundle_id="test_bundle",
            created_at="2024-01-01T00:00:00Z",
        )

        json_path = tmp_path / "debug_bundle.json"
        bundle.to_json(json_path)

        assert json_path.exists()

        with open(json_path) as f:
            loaded = json.load(f)

        assert loaded["bundle_id"] == "test_bundle"


class TestEmitDebugBundle:
    """Tests for emit_debug_bundle function."""

    def test_emit_empty_bundle(self):
        """Test emitting empty debug bundle."""
        bundle = emit_debug_bundle()

        assert bundle.bundle_id.startswith("debug_bundle_")
        assert len(bundle.redacted_replay) == 0

    def test_emit_with_entries(self):
        """Test emitting bundle with entries."""
        entries = [
            {"content": "User asked about test@example.com", "type": "prompt"},
            {"content": "Response about john.doe@test.com", "type": "response"},
        ]

        bundle = emit_debug_bundle(entries=entries)

        assert len(bundle.redacted_replay) == 2
        # Verify privacy redaction applied
        for entry in bundle.redacted_replay:
            assert "@test.com" not in entry.redacted_content

    def test_emit_with_synthetic(self):
        """Test emitting bundle with synthetic replay."""
        entries = [
            {"content": "Test content", "type": "prompt"},
        ]

        bundle = emit_debug_bundle(
            entries=entries,
            include_synthetic=True,
        )

        assert bundle.synthetic_replay is not None
        assert len(bundle.synthetic_replay) > 0
        for entry in bundle.synthetic_replay:
            assert "[SYNTHETIC]" in entry.synthetic_content

    def test_emit_with_output_path(self, tmp_path):
        """Test emitting bundle to file."""
        emit_debug_bundle(
            entries=[{"content": "Test", "type": "prompt"}],
            bundle_id="test_output",
            output_path=tmp_path / "debug.json",
        )

        assert (tmp_path / "debug.json").exists()

    def test_no_raw_private_in_bundle(self):
        """Verify no raw private text is exported."""
        private_entries = [
            {"content": "My SSN is 123-45-6789", "type": "prompt"},
            {"content": "Phone: 555-987-6543", "type": "response"},
        ]

        bundle = emit_debug_bundle(entries=private_entries)

        # Check redacted replay
        for entry in bundle.redacted_replay:
            # Should NOT contain raw SSN or phone
            assert "123-45-6789" not in entry.redacted_content
            assert "555-987-6543" not in entry.redacted_content
            # Should contain placeholders
            assert "[REDACTED_" in entry.redacted_content
