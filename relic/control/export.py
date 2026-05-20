"""Export functionality for user data portability.

This module provides secure export of user data with proper
redaction and privacy controls.
"""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from relic.db import get_connection


class ExportFormat(str, Enum):
    """Supported export formats."""
    JSON = "json"
    JSONL = "jsonl"
    MARKDOWN = "markdown"


class ExportOptions(BaseModel):
    """Options for export operation."""
    include_prompts: bool = True
    include_corrections: bool = True
    include_artifacts: bool = True
    include_consent: bool = True
    redact_content: bool = True
    session_id: UUID | None = None


class ExportResult(BaseModel):
    """Result of an export operation."""
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    format: ExportFormat
    record_count: int = 0
    artifact_count: int = 0
    file_path: Path | None = None
    checksum: str = ""
    redacted: bool = True


class ExportManager:
    """Manages secure export of user data."""

    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = db_path

    def export(
        self,
        output_path: Path,
        format: ExportFormat = ExportFormat.JSON,
        options: ExportOptions | None = None,
        *,
        accessor_id: str = "researcher:control",
        subject_id: str | None = None,
    ) -> ExportResult:
        """Export user data to the specified format.

        Every export is recorded as a Chronicle `export` access event so the
        governance docs' "every export is audited" claim holds for this surface
        too (not only the Chronicle CLI). Audit logging is fail-open: an audit
        failure must never block or corrupt the export itself.
        """
        opts = options or ExportOptions()

        data: dict[str, Any] = {
            "exported_at": datetime.utcnow().isoformat(),
            "format": format.value,
            "options": opts.model_dump(),
        }

        if opts.include_prompts:
            data["prompts"] = self._export_prompts(opts)

        if opts.include_corrections:
            data["corrections"] = self._export_corrections(opts)

        if opts.include_artifacts:
            data["artifacts"] = self._export_artifacts(opts)

        if opts.include_consent:
            data["consent"] = self._export_consent(opts)

        total_records = (
            len(data.get("prompts", []))
            + len(data.get("corrections", []))
            + len(data.get("consent", []))
        )

        if format == ExportFormat.JSON:
            output_path.write_text(json.dumps(data, indent=2, default=str))
        elif format == ExportFormat.JSONL:
            lines = [
                json.dumps({"type": k, "data": v}) if isinstance(v, list) else json.dumps({"type": k, "data": v})
                for k, v in data.items()
            ]
            output_path.write_text("\n".join(lines))
        elif format == ExportFormat.MARKDOWN:
            output_path.write_text(self._to_markdown(data))

        record_count = total_records
        artifact_count = len(data.get("artifacts", []))

        # Audit the export (fail-open).
        try:
            from relic.chronicle.access_audit import log_export

            bytes_written = output_path.stat().st_size if output_path.exists() else 0
            log_export(
                accessor_id=accessor_id,
                subject_id=subject_id or (str(opts.session_id) if opts.session_id else "unknown"),
                format=format.value,
                bytes_written=bytes_written,
            )
        except Exception:  # noqa: BLE001 - audit must never block export
            import logging
            logging.getLogger(__name__).warning(
                "[control.export] access audit logging failed", exc_info=True
            )

        return ExportResult(
            format=format,
            record_count=record_count,
            artifact_count=artifact_count,
            file_path=output_path,
            redacted=opts.redact_content,
        )

    def _export_prompts(self, opts: ExportOptions) -> list[dict[str, Any]]:
        """Export prompt records."""
        conn = get_connection(self._db_path)
        try:
            cur = conn.cursor()
            if opts.session_id:
                cur.execute(
                    "SELECT * FROM prompt_records WHERE session_id = ?",
                    (str(opts.session_id),),
                )
            else:
                cur.execute("SELECT * FROM prompt_records")
            rows = cur.fetchall()
        finally:
            conn.close()

        results = []
        for row in rows:
            record = dict(row)
            if opts.redact_content:
                record["content_hash"] = "[REDACTED_HASH]"
                record["content_length"] = 0
            record["id"] = str(record["id"])
            record["session_id"] = str(record["session_id"]) if record["session_id"] else None
            record["original_prompt_id"] = str(record["original_prompt_id"]) if record["original_prompt_id"] else None
            results.append(record)

        return results

    def _export_corrections(self, opts: ExportOptions) -> list[dict[str, Any]]:
        """Export correction records."""
        conn = get_connection(self._db_path)
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM correction_records")
            rows = cur.fetchall()
        finally:
            conn.close()

        results = []
        for row in rows:
            record = dict(row)
            record["id"] = str(record["id"])
            record["prompt_id"] = str(record["prompt_id"])
            if opts.redact_content:
                record["delta_content"] = "[REDACTED]"
            results.append(record)

        return results

    def _export_artifacts(self, opts: ExportOptions) -> list[dict[str, Any]]:
        """Export artifact records."""
        conn = get_connection(self._db_path)
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM artifact_records")
            rows = cur.fetchall()
        finally:
            conn.close()

        results = []
        for row in rows:
            record = dict(row)
            record["id"] = str(record["id"])
            record["session_id"] = str(record["session_id"]) if record["session_id"] else None
            if opts.redact_content:
                record["artifact_hash"] = "[REDACTED_HASH]"
            results.append(record)

        return results

    def _export_consent(self, opts: ExportOptions) -> list[dict[str, Any]]:
        """Export consent records."""
        conn = get_connection(self._db_path)
        try:
            cur = conn.cursor()
            if opts.session_id:
                cur.execute(
                    "SELECT * FROM consent_records WHERE session_id = ?",
                    (str(opts.session_id),),
                )
            else:
                cur.execute("SELECT * FROM consent_records")
            rows = cur.fetchall()
        finally:
            conn.close()

        results = []
        for row in rows:
            record = dict(row)
            record["id"] = str(record["id"])
            record["session_id"] = str(record["session_id"]) if record["session_id"] else None
            results.append(record)

        return results

    def _to_markdown(self, data: dict[str, Any]) -> str:
        """Convert export data to markdown format."""
        lines = [
            "# Relic Data Export",
            "",
            f"**Exported at:** {data.get('exported_at', 'unknown')}",
            "",
        ]

        for section, content in data.items():
            if section in ("exported_at", "format", "options"):
                continue

            lines.append(f"## {section.replace('_', ' ').title()}")
            lines.append("")

            if isinstance(content, list) and content:
                for item in content:
                    lines.append(f"- {json.dumps(item, default=str)}")
            else:
                lines.append(str(content))

            lines.append("")

        return "\n".join(lines)
