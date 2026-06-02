"""
Async emit queue for Chronicle events with per-category drop policy.

Safety, privacy, and consent events use NEVER drop policy (block briefly if
queue is full). All other events use configurable eviction policies so that
a slow Chronicle write path never stalls the LLM turn.
"""
from __future__ import annotations

import logging
import queue
import threading
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional
from uuid import UUID

from relic.chronicle.enums import EventCategory

_logger = logging.getLogger(__name__)


class DropPolicy(str, Enum):
    NEVER = "never"          # block until space, audit-critical
    DROP_OLDEST = "drop_oldest"  # evict head when full
    DROP_NEW = "drop_new"    # discard new entry when full


# Per-category policy.  SAFETY/PRIVACY/CONSENT → never drop.
_CATEGORY_POLICY: dict[EventCategory, DropPolicy] = {
    EventCategory.SAFETY: DropPolicy.NEVER,
    EventCategory.PRIVACY: DropPolicy.NEVER,
    EventCategory.CONSENT: DropPolicy.NEVER,
    EventCategory.DECISION: DropPolicy.DROP_OLDEST,
    EventCategory.ERROR: DropPolicy.DROP_OLDEST,
    EventCategory.BACKGROUND: DropPolicy.DROP_NEW,
    EventCategory.MEMORY: DropPolicy.DROP_NEW,
    EventCategory.MODEL: DropPolicy.DROP_NEW,
    EventCategory.MESSAGE: DropPolicy.DROP_OLDEST,
    EventCategory.TOOL: DropPolicy.DROP_OLDEST,
    EventCategory.PROFILE: DropPolicy.DROP_OLDEST,
    EventCategory.ARTIFACT: DropPolicy.DROP_OLDEST,
    EventCategory.ADMIN: DropPolicy.DROP_OLDEST,
    EventCategory.EVAL: DropPolicy.DROP_NEW,
    EventCategory.STATE_SNAPSHOT: DropPolicy.DROP_NEW,
    EventCategory.PROVENANCE: DropPolicy.DROP_OLDEST,
}


@dataclass
class EmitTask:
    """Pending emit call with routing metadata."""
    category: EventCategory
    fn: Callable[..., UUID]
    kwargs: dict[str, Any]

    def execute(self) -> UUID:
        return self.fn(**self.kwargs)


class ChronicleEmitQueue:
    """Bounded background queue for async Chronicle event emission.

    Usage::

        queue = ChronicleEmitQueue()
        queue.submit(EmitTask(category, emit_event, kwargs))
        # ... on shutdown:
        queue.flush()
    """

    def __init__(self, maxsize: int = 500, drain_timeout: float = 5.0):
        self._maxsize = maxsize
        self._drain_timeout = drain_timeout
        self._queue: queue.Queue[EmitTask] = queue.Queue(maxsize=maxsize)
        self._stopped = threading.Event()
        self._thread = threading.Thread(
            target=self._drain,
            daemon=True,
            name="chronicle-emit-queue",
        )
        self._thread.start()

    def submit(self, task: EmitTask) -> bool:
        """Enqueue task. Returns True if accepted.

        For NEVER policy (safety events): blocks until space is available.
        For DROP_NEW: returns False and logs if full.
        For DROP_OLDEST: evicts oldest entry to make room.
        """
        if self._stopped.is_set():
            # Shutdown in progress: emit synchronously as fallback.
            try:
                task.execute()
            except Exception as exc:
                _logger.error("chronicle emit failed during shutdown: %s", exc)
            return True

        policy = _CATEGORY_POLICY.get(task.category, DropPolicy.DROP_OLDEST)

        try:
            if policy == DropPolicy.NEVER:
                self._queue.put(task)  # blocks, must not lose safety events
                return True

            if policy == DropPolicy.DROP_NEW:
                try:
                    self._queue.put_nowait(task)
                    return True
                except queue.Full:
                    _logger.warning(
                        "emit_queue full: dropping %s event (DROP_NEW)",
                        task.category.value,
                    )
                    return False

            # DROP_OLDEST: evict head, then enqueue
            try:
                self._queue.put_nowait(task)
                return True
            except queue.Full:
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    pass
                self._queue.put_nowait(task)
                return True

        except Exception as exc:
            _logger.error("emit_queue.submit error: %s", exc)
            return False

    def _drain(self) -> None:
        while not self._stopped.is_set():
            try:
                task = self._queue.get(timeout=0.2)
                try:
                    task.execute()
                except Exception as exc:
                    _logger.error(
                        "chronicle emit failed for %s: %s",
                        task.category.value,
                        exc,
                    )
            except queue.Empty:
                continue

    def flush(self, timeout: Optional[float] = None) -> None:
        """Drain remaining tasks and stop the background thread."""
        self._stopped.set()
        self._thread.join(timeout=timeout or self._drain_timeout)

    def qsize(self) -> int:
        return self._queue.qsize()


_default_queue: Optional[ChronicleEmitQueue] = None
_queue_lock = threading.Lock()


def get_emit_queue() -> ChronicleEmitQueue:
    """Return the process-level emit queue (lazy init, thread-safe)."""
    global _default_queue
    if _default_queue is None:
        with _queue_lock:
            if _default_queue is None:
                _default_queue = ChronicleEmitQueue()
    return _default_queue
