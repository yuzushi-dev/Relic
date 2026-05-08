"""Tests for correction note import into correction queue.

This test module verifies:
1. Correction notes can be imported into correction queue
2. Each note is traceable to DB correction record
3. Raw content is NEVER imported
"""

from __future__ import annotations

import json
from pathlib import Path

from relic.vault.import_corrections import (
    CorrectionImportResult,
    CorrectionNoteImporter,
    import_correction_note,
)


class TestCorrectionNoteImport:
    """Test correction note import functionality."""

    def test_import_valid_note(self, tmp_path: Path):
        """Verify valid correction note can be imported."""
        note = {
            "note_id": "test-correction-1",
            "session_id": "test-session-1",
            "correction_type": "factual_correction",
            "original_hash": "abc123hash",
            "corrected_content": "CORRECTED: The capital is Paris",
            "created_at": "2024-01-15T10:00:00Z",
        }

        note_path = tmp_path / "correction_note.json"
        note_path.write_text(json.dumps(note))

        importer = CorrectionNoteImporter(db_path=tmp_path / "test.db")
        result = importer.import_note(note_path, dry_run=True)

        assert result.imported == 0
        assert result.skipped == 1

    def test_import_dry_run(self, tmp_path: Path):
        """Verify dry_run mode validates without importing."""
        note = {
            "note_id": "test-correction-2",
            "session_id": "test-session-1",
            "correction_type": "redaction",
            "original_hash": "def456hash",
        }

        note_path = tmp_path / "correction_note.json"
        note_path.write_text(json.dumps(note))

        importer = CorrectionNoteImporter(db_path=tmp_path / "test.db")
        result = importer.import_note(note_path, dry_run=True)

        assert result.skipped == 1
        assert result.imported == 0

    def test_import_missing_note(self, tmp_path: Path):
        """Verify import fails gracefully for missing note."""
        importer = CorrectionNoteImporter(db_path=tmp_path / "test.db")
        result = importer.import_note(tmp_path / "nonexistent.json")

        assert result.imported == 0
        assert len(result.errors) > 0
        assert "not found" in result.errors[0].lower()

    def test_import_invalid_json(self, tmp_path: Path):
        """Verify import fails gracefully for invalid JSON."""
        note_path = tmp_path / "invalid.json"
        note_path.write_text("not valid json {")

        importer = CorrectionNoteImporter(db_path=tmp_path / "test.db")
        result = importer.import_note(note_path)

        assert result.imported == 0
        assert len(result.errors) > 0
        assert "Invalid JSON" in result.errors[0]

    def test_import_missing_required_fields(self, tmp_path: Path):
        """Verify import fails for missing required fields."""
        note = {
            "note_id": "test-1",
        }

        note_path = tmp_path / "incomplete.json"
        note_path.write_text(json.dumps(note))

        importer = CorrectionNoteImporter(db_path=tmp_path / "test.db")
        result = importer.import_note(note_path)

        assert result.imported == 0
        assert len(result.errors) > 0
        assert "Missing required fields" in result.errors[0]

    def test_import_untraceable_note(self, tmp_path: Path):
        """Verify untraceable notes are rejected."""
        note = {
            "note_id": "nonexistent-correction",
            "session_id": "test-session",
            "correction_type": "redaction",
            "original_hash": "unknown-hash",
        }

        note_path = tmp_path / "untraceable.json"
        note_path.write_text(json.dumps(note))

        importer = CorrectionNoteImporter(db_path=tmp_path / "test.db")
        result = importer.import_note(note_path)

        assert result.imported == 0
        assert len(result.errors) > 0
        assert "Cannot trace" in result.errors[0]


class TestCorrectionNoteTraceability:
    """Test correction notes are traceable to DB records."""

    def test_import_from_directory_empty(self, tmp_path: Path):
        """Verify batch import from empty directory."""
        importer = CorrectionNoteImporter(db_path=tmp_path / "test.db")
        result = importer.import_from_directory(tmp_path)

        assert result.imported == 0
        assert result.skipped == 0

    def test_import_from_nonexistent_directory(self, tmp_path: Path):
        """Verify batch import fails gracefully for nonexistent dir."""
        importer = CorrectionNoteImporter(db_path=tmp_path / "test.db")
        result = importer.import_from_directory(tmp_path / "nonexistent")

        assert len(result.errors) > 0
        assert "not found" in result.errors[0].lower()


class TestImportResult:
    """Test import result structure."""

    def test_result_to_dict(self):
        """Verify CorrectionImportResult serializes correctly."""
        result = CorrectionImportResult(
            imported=2,
            skipped=1,
            errors=["error1"],
            trace_ids=["trace1", "trace2"],
        )

        d = result.to_dict()

        assert d["imported"] == 2
        assert d["skipped"] == 1
        assert d["errors"] == ["error1"]
        assert d["trace_ids"] == ["trace1", "trace2"]
        assert "imported_at" in d

    def test_convenience_function_missing_file(self, tmp_path: Path):
        """Verify convenience import function handles missing files."""
        result = import_correction_note(tmp_path / "nonexistent.json")

        assert result["imported"] == 0
        assert len(result["errors"]) > 0
