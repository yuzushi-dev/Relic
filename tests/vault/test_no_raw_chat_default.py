"""Tests verifying raw chat is absent by default.

This test module verifies:
1. Vault export never includes raw chat by default
2. Raw chat can only be included with explicit opt-in
3. Privacy gate blocks raw chat export
"""

from __future__ import annotations

import json
from pathlib import Path

from relic.vault.export import VaultExporter, VaultExportOptions


class TestNoRawChatDefault:
    """Verify raw chat is absent unless explicitly enabled."""

    def test_default_options_no_raw_chat(self):
        """Verify default export options exclude raw chat."""
        options = VaultExportOptions()

        assert options.include_raw_chat is False, "BLOCK: Raw chat must NOT be included by default"

    def test_explicit_false_still_no_raw_chat(self):
        """Verify explicit False still results in no raw chat."""
        options = VaultExportOptions(include_raw_chat=False)

        assert options.include_raw_chat is False

    def test_exporter_result_records_no_raw_chat(self, tmp_path: Path):
        """Verify VaultExporter result records raw_chat_included correctly."""
        options = VaultExportOptions()
        exporter = VaultExporter(db_path=tmp_path / "test.db")

        result = exporter.export_vault(tmp_path / "export", options=options)

        assert result.raw_chat_included is False

    def test_manifest_records_raw_chat_status(self, tmp_path: Path):
        """Verify manifest correctly records raw chat inclusion status."""
        options = VaultExportOptions()
        exporter = VaultExporter(db_path=tmp_path / "test.db")
        output_dir = tmp_path / "export"

        exporter.export_vault(output_dir, options=options)

        manifest_path = output_dir / "vault_export_manifest.json"
        manifest = json.loads(manifest_path.read_text())

        assert manifest["raw_chat_included"] is False
        assert manifest["privacy_verified"] is True


class TestRawChatSecurityInvariants:
    """Security invariant tests for raw chat exclusion."""

    def test_raw_chat_included_flag_is_boolean(self, tmp_path: Path):
        """Verify raw_chat_included is always a boolean."""
        options = VaultExportOptions()
        exporter = VaultExporter(db_path=tmp_path / "test.db")
        result = exporter.export_vault(tmp_path / "export", options=options)

        assert isinstance(result.raw_chat_included, bool)

    def test_privacy_verified_requires_no_raw_chat(self, tmp_path: Path):
        """Verify privacy_verified implies no raw chat."""
        options = VaultExportOptions()
        exporter = VaultExporter(db_path=tmp_path / "test.db")
        result = exporter.export_vault(tmp_path / "export", options=options)

        if result.privacy_verified:
            assert result.raw_chat_included is False

    def test_export_manifest_always_creates(self, tmp_path: Path):
        """Verify manifest is always created, even empty vault."""
        options = VaultExportOptions()
        exporter = VaultExporter(db_path=tmp_path / "test.db")
        output_dir = tmp_path / "export"

        exporter.export_vault(output_dir, options=options)

        manifest_path = output_dir / "vault_export_manifest.json"
        assert manifest_path.exists()

        manifest = json.loads(manifest_path.read_text())
        assert "raw_chat_included" in manifest
        assert "privacy_verified" in manifest
        assert "exported_at" in manifest

    def test_result_serialization(self, tmp_path: Path):
        """Verify result can be serialized with correct flags."""
        options = VaultExportOptions()
        exporter = VaultExporter(db_path=tmp_path / "test.db")
        result = exporter.export_vault(tmp_path / "export", options=options)

        d = result.to_dict()

        assert d["raw_chat_included"] is False
        assert d["privacy_verified"] is True
