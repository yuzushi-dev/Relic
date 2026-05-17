"""
StateStore — Durable JSON persistence for adapter governance state.

In-memory dicts (consent store, pending approvals) are lost on restart.
This module provides a lightweight file-based store backed by
~/.relic/adapter_state/ so governance facts survive process restarts
without requiring DB schema changes.

Each store is a dict serialised as an atomic JSON file (write → fsync → rename).
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from pathlib import Path
from typing import Any, Optional

_logger = logging.getLogger(__name__)


def _state_dir() -> Path:
    base = Path(os.environ.get("RELIC_STATE_DIR", Path.home() / ".relic" / "adapter_state"))
    base.mkdir(parents=True, exist_ok=True)
    return base


class StateStore:
    """Thread-safe durable dict backed by a JSON file.

    Reads on first access, writes atomically (tmp file → rename).

    Args:
        name: Store name used as filename stem (e.g. "consent_store").
        state_dir: Override the directory (defaults to ~/.relic/adapter_state/).
    """

    def __init__(self, name: str, state_dir: Optional[Path] = None):
        self._path = (state_dir or _state_dir()) / f"{name}.json"
        self._lock = threading.Lock()
        self._data: Optional[dict[str, Any]] = None

    def _load(self) -> dict[str, Any]:
        if self._data is None:
            if self._path.exists():
                try:
                    with self._path.open("r", encoding="utf-8") as fh:
                        self._data = json.load(fh)
                except Exception as exc:
                    _logger.error("state_store: failed to load %s: %s", self._path, exc)
                    self._data = {}
            else:
                self._data = {}
        return self._data

    def _save(self) -> None:
        try:
            dir_path = self._path.parent
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=dir_path,
                delete=False,
                suffix=".tmp",
            ) as fh:
                json.dump(self._data, fh, indent=2, default=str)
                fh.flush()
                os.fsync(fh.fileno())
                tmp_path = fh.name
            os.replace(tmp_path, self._path)
        except Exception as exc:
            _logger.error("state_store: failed to save %s: %s", self._path, exc)

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._load().get(key, default)

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._load()[key] = value
            self._save()

    def delete(self, key: str) -> None:
        with self._lock:
            data = self._load()
            if key in data:
                del data[key]
                self._save()

    def all(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._load())

    def keys(self) -> list[str]:
        with self._lock:
            return list(self._load().keys())

    def __contains__(self, key: str) -> bool:
        with self._lock:
            return key in self._load()

    def __len__(self) -> int:
        with self._lock:
            return len(self._load())
