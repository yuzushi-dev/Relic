"""Tests for vault regeneration capability.

This test module verifies:
1. Vault can be deleted and regenerated
2. Regeneration does not require raw chat
3. Privacy verification passes
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from relic.vault.export import (
    VaultExporter,
    VaultExportOptions,
    regenerate_vault,
)


class TestVaultRegeneration:
    """Test vault can be deleted and regenerated."""

    def test_regenerate_from_export(self, tmp_path: Path):
        """Verify vault can be regenerated from export without raw chat."""
        export_dir = tmp_path / "export"
        export_dir.mkdir()

        manifest = {
            "export_path": str(export_dir),
            "sessions": [
                {
                    "session_id": "test-session-1",
                    "created_at": "2024-01-15T10:00:00Z",
                    "privacy_level": "safe",
                    "content_hash": "abc123",
                    "prompt_count": 5,
                    "correction_count": 1,
                    "last_activity": "2024-01-15T11:00:00Z",
                }
            ],
            "profiles": [
                {
                    "profile_id": "test-profile-1",
                    "created_at": "2024-01-01T00:00:00Z",
                    "privacy_level": "safe",
                    "content_hash": "def456",
                    "session_count": 1,
                    "preference_count": 3,
                }
            ],
            "corrections": [],
            "audit_log": [],
            "exported_at": "2024-01-15T12:00:00Z",
            "options_used": {
                "include_sessions": True,
                "include_profiles": True,
                "include_corrections": True,
                "include_audit": True,
                "include_raw_chat": False,
                "redact_private": True,
            },
            "raw_chat_included": False,
            "privacy_verified": True,
        }

        manifest_path = export_dir / "vault_export_manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        report = regenerate_vault(export_dir)

        assert report["sessions_regenerated"] == 1
        assert report["profiles_regenerated"] == 1
        assert report["privacy_verified"] is True
        assert "regenerated_at" in report

    def test_regenerate_blocks_raw_chat_export(self, tmp_path: Path):
        """Verify regeneration fails if raw chat was exported."""
        export_dir = tmp_path / "export"
        export_dir.mkdir()

        manifest = {
            "export_path": str(export_dir),
            "sessions": [],
            "profiles": [],
            "corrections": [],
            "audit_log": [],
            "exported_at": "2024-01-15T12:00:00Z",
            "options_used": {"include_raw_chat": False},
            "raw_chat_included": True,
            "privacy_verified": True,
        }

        manifest_path = export_dir / "vault_export_manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        with pytest.raises(AssertionError, match="raw chat cannot be regenerated"):
            regenerate_vault(export_dir)

    def test_regenerate_requires_manifest(self, tmp_path: Path):
        """Verify regeneration fails without manifest."""
        with pytest.raises(FileNotFoundError):
            regenerate_vault(tmp_path)


class TestVaultExporterOptions:
    """Test vault export options."""

    def test_default_options_no_raw_chat(self):
        """Verify default export options exclude raw chat."""
        options = VaultExportOptions()

        assert options.include_raw_chat is False, "BLOCK: Raw chat must NOT be included by default"

    def test_explicit_false_no_raw_chat(self):
        """Verify explicit False still results in no raw chat."""
        options = VaultExportOptions(include_raw_chat=False)

        assert options.include_raw_chat is False

    def test_export_options_defaults(self):
        """Verify default export options are privacy-safe."""
        options = VaultExportOptions()

        assert options.include_sessions is True
        assert options.include_profiles is True
        assert options.include_corrections is True
        assert options.include_audit is True
        assert options.redact_private is True


class TestVaultExportResult:
    """Test vault export result structure."""

    def test_result_has_required_fields(self, tmp_path: Path):
        """Verify result has all required security fields."""
        options = VaultExportOptions()
        exporter = VaultExporter(db_path=tmp_path / "nonexistent.db")

        result = exporter.export_vault(tmp_path / "export", options=options)

        assert hasattr(result, "raw_chat_included")
        assert hasattr(result, "privacy_verified")
        assert hasattr(result, "exported_at")
        assert result.raw_chat_included is False
        assert result.options_used["include_raw_chat"] is False
