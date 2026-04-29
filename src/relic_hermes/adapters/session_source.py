"""Hermes-backed session transcript access."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from relic_core.interfaces import SessionMessage, SessionRecord


class HermesSessionSource:
    """Read Hermes transcript state without assuming legacy agent directories."""

    def __init__(
        self,
        sessions_dir: str | Path,
        sessions_index: str | Path | None = None,
        db_path: str | Path | None = None,
    ) -> None:
        self.sessions_dir = Path(sessions_dir)
        self.sessions_index = (
            Path(sessions_index)
            if sessions_index is not None
            else self.sessions_dir / "sessions.json"
        )
        self.db_path = Path(db_path) if db_path is not None else self.sessions_dir.parent / "state.db"

    def list_recent_sessions(self, *, since: datetime | None = None) -> list[SessionRecord]:
        records_by_id: dict[str, SessionRecord] = {}
        for session_key, entry in self._iter_session_entries():
            session_id = str(entry.get("session_id", "")).strip()
            if not session_id:
                continue
            updated_at = self._resolve_updated_at(session_id, entry)
            if updated_at is None:
                continue
            if since is not None and updated_at < since:
                continue
            record = self._build_record(session_id, updated_at, session_key, entry)
            current = records_by_id.get(session_id)
            if current is None or record.updated_at > current.updated_at:
                records_by_id[session_id] = record
        records = list(records_by_id.values())
        records.sort(key=lambda record: record.updated_at, reverse=True)
        return records

    def load_transcript(self, session: SessionRecord | str) -> list[SessionMessage]:
        session_id = session.session_id if isinstance(session, SessionRecord) else str(session)
        session_key = session.session_key if isinstance(session, SessionRecord) else None
        messages = self._load_transcript_from_db(session_id, session_key=session_key)
        if messages:
            return messages
        messages = self._load_transcript_from_session_file(session_id, session_key=session_key)
        if messages:
            return messages
        return self._load_transcript_from_jsonl(session_id, session_key=session_key)

    def _load_index(self) -> dict[str, dict]:
        if not self.sessions_index.exists():
            return {}
        try:
            payload = json.loads(self.sessions_index.read_text(encoding="utf-8"))
        except Exception:
            return {}
        if not isinstance(payload, dict):
            return {}
        return {
            str(key): value
            for key, value in payload.items()
            if isinstance(value, dict)
        }

    def _iter_session_entries(self) -> list[tuple[str | None, dict]]:
        entries: list[tuple[str | None, dict]] = []
        seen_session_ids: set[str] = set()

        for session_key, entry in self._load_index().items():
            session_id = str(entry.get("session_id", "")).strip()
            if session_id:
                seen_session_ids.add(session_id)
            entries.append((session_key, entry))

        for path in sorted(self.sessions_dir.glob("session_*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue
            session_id = str(payload.get("session_id", "")).strip()
            if not session_id or session_id in seen_session_ids:
                continue
            seen_session_ids.add(session_id)
            entries.append((None, payload | {"_session_file": str(path)}))

        for entry in self._load_sessions_from_db():
            session_id = str(entry.get("session_id", "")).strip()
            if not session_id or session_id in seen_session_ids:
                continue
            seen_session_ids.add(session_id)
            entries.append((None, entry))

        return entries

    def _load_sessions_from_db(self) -> list[dict]:
        if not self.db_path.exists():
            return []
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT id, source, started_at, ended_at, message_count, title, model "
                "FROM sessions ORDER BY COALESCE(ended_at, started_at) DESC"
            ).fetchall()
        except sqlite3.Error:
            rows = []
        finally:
            conn.close()
        entries: list[dict] = []
        for row in rows:
            entries.append(
                {
                    "session_id": row["id"],
                    "updated_at": self._timestamp_to_iso(row["ended_at"] or row["started_at"]),
                    "platform": row["source"],
                    "message_count": row["message_count"],
                    "title": row["title"],
                    "model": row["model"],
                }
            )
        return entries

    def _resolve_updated_at(self, session_id: str, entry: dict) -> datetime | None:
        updated_at = self._parse_updated_at(entry.get("updated_at"))
        if updated_at is None:
            updated_at = self._parse_updated_at(entry.get("last_updated"))
        if updated_at is not None:
            return updated_at

        transcript_path = self.sessions_dir / f"{session_id}.jsonl"
        if transcript_path.exists():
            return datetime.fromtimestamp(transcript_path.stat().st_mtime, tz=timezone.utc)

        session_file_path = self.sessions_dir / f"session_{session_id}.json"
        if session_file_path.exists():
            return datetime.fromtimestamp(session_file_path.stat().st_mtime, tz=timezone.utc)

        return None

    def _build_record(
        self,
        session_id: str,
        updated_at: datetime,
        session_key: str | None,
        entry: dict,
    ) -> SessionRecord:
        transcript_path = self.sessions_dir / f"{session_id}.jsonl"
        session_file_path = self.sessions_dir / f"session_{session_id}.json"
        size_bytes = None
        if transcript_path.exists():
            size_bytes = transcript_path.stat().st_size
        elif session_file_path.exists():
            size_bytes = session_file_path.stat().st_size
        return SessionRecord(
            session_id=session_id,
            updated_at=updated_at,
            state_key=f"hermes:{session_id}",
            session_key=session_key,
            size_bytes=size_bytes,
            metadata={
                "transcript_path": str(transcript_path),
                "session_file_path": str(session_file_path),
                "session_key": session_key,
                "raw_index": entry,
                "platform": entry.get("platform"),
            },
        )

    def _load_transcript_from_db(
        self,
        session_id: str,
        *,
        session_key: str | None,
    ) -> list[SessionMessage]:
        if not self.db_path.exists():
            return []
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT role, content, tool_name, tool_calls, timestamp "
                "FROM messages WHERE session_id = ? ORDER BY timestamp, id",
                (session_id,),
            ).fetchall()
        except sqlite3.Error:
            rows = []
        finally:
            conn.close()

        messages: list[SessionMessage] = []
        for row in rows:
            content = row["content"] or ""
            tool_calls = row["tool_calls"]
            raw: dict[str, object] = {
                "role": row["role"],
                "content": content,
                "tool_name": row["tool_name"],
            }
            parsed_tool_calls: object = None
            if tool_calls:
                try:
                    parsed_tool_calls = json.loads(tool_calls)
                except Exception:
                    parsed_tool_calls = tool_calls
                raw["tool_calls"] = parsed_tool_calls

            timestamp = None
            if row["timestamp"] is not None:
                timestamp = datetime.fromtimestamp(float(row["timestamp"]), tz=timezone.utc).isoformat()

            messages.append(
                SessionMessage(
                    role=str(row["role"] or "unknown"),
                    content=str(content),
                    session_id=session_id,
                    session_key=session_key,
                    timestamp=timestamp,
                    metadata={"raw": raw},
                )
            )
        return messages

    def _load_transcript_from_jsonl(
        self,
        session_id: str,
        *,
        session_key: str | None,
    ) -> list[SessionMessage]:
        transcript_path = self.sessions_dir / f"{session_id}.jsonl"
        if not transcript_path.exists():
            return []
        messages: list[SessionMessage] = []
        with transcript_path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                role = str(item.get("role", "unknown"))
                content = item.get("content", "")
                if isinstance(content, list):
                    content = " ".join(
                        block.get("text", "") if isinstance(block, dict) else str(block)
                        for block in content
                    )
                messages.append(
                    SessionMessage(
                        role=role,
                        content=str(content or ""),
                        session_id=session_id,
                        session_key=session_key,
                        timestamp=item.get("timestamp"),
                        metadata={"raw": item},
                    )
                )
        return messages

    def _load_transcript_from_session_file(
        self,
        session_id: str,
        *,
        session_key: str | None,
    ) -> list[SessionMessage]:
        session_file_path = self.sessions_dir / f"session_{session_id}.json"
        if not session_file_path.exists():
            return []
        try:
            payload = json.loads(session_file_path.read_text(encoding="utf-8"))
        except Exception:
            return []
        raw_messages = payload.get("messages")
        if not isinstance(raw_messages, list):
            return []

        messages: list[SessionMessage] = []
        for item in raw_messages:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role", "unknown"))
            content = item.get("content", "")
            if isinstance(content, list):
                content = " ".join(
                    block.get("text", "") if isinstance(block, dict) else str(block)
                    for block in content
                )
            messages.append(
                SessionMessage(
                    role=role,
                    content=str(content or ""),
                    session_id=session_id,
                    session_key=session_key,
                    timestamp=item.get("timestamp"),
                    metadata={"raw": item},
                )
            )
        return messages

    def _parse_updated_at(self, value: object) -> datetime | None:
        if not isinstance(value, str) or not value.strip():
            return None
        parsed = value.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(parsed)
        except ValueError:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def _timestamp_to_iso(self, value: object) -> str | None:
        if value is None:
            return None
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat()
        except (TypeError, ValueError, OSError):
            return None
