"""Hermes MemoryProvider for Relic shared continuity (PR06).

Implements the Hermes MemoryProvider interface so confirmed continuity
markers are surfaced into the LLM context via prefetch(), and new
conversational traces are committed via sync_turn().

Constraints:
- Only subject_confirmation=TRUE markers are prefetched.
- Raw user/assistant text is NEVER stored; only redacted hashes via
  PrivacyTrace.  sync_turn() records a trace, not raw content.
- PR32 sensitive_signal objects are never prefetched (origin guard).
- Fail-open: every public method catches all exceptions and returns a
  safe default so Hermes never blocks a conversation on plugin error.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_REDACTED = "[redacted]"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


class RelicMemoryProvider:
    """Hermes MemoryProvider backed by Relic shared-continuity store.

    Usage inside plugin registration (called once per session)::

        provider = RelicMemoryProvider(subject_id=subject_id)
        ctx.register_memory_provider(provider)
    """

    def __init__(
        self,
        subject_id: str,
        gumi_instance_id: str | None = None,
        hermes_profile_id: str | None = None,
        max_prefetch: int = 5,
    ) -> None:
        self._subject_id = subject_id
        self._gumi_instance_id = gumi_instance_id or ""
        self._hermes_profile_id = hermes_profile_id or ""
        self._max_prefetch = max_prefetch
        self._store = None  # lazy

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_store(self):
        if self._store is None:
            from relic.gumi_continuity.store import GumiContinuityStore
            self._store = GumiContinuityStore()
        return self._store

    def _is_safe_to_surface(self, marker: dict[str, Any]) -> bool:
        """Return False for any marker that must not reach LLM context."""
        # PR32: never surface sensitive_signal-origin markers
        if marker.get("origin") == "sensitive_signal":
            return False
        # Only confirmed markers
        if not marker.get("subject_confirmation", False):
            return False
        return True

    def _format_marker(self, marker: dict[str, Any]) -> str:
        """Convert a continuity marker to a compact human-readable line."""
        words = marker.get("subject_words") or marker.get("words") or []
        if isinstance(words, list):
            text = " ".join(str(w) for w in words)
        else:
            text = str(words)
        return text.strip() if text.strip() else _REDACTED

    # ------------------------------------------------------------------
    # Hermes MemoryProvider API
    # ------------------------------------------------------------------

    def prefetch(self, query: str) -> str:
        """Return confirmed continuity items as plain text for context injection.

        Called by Hermes at pre_llm_call time. Returns an empty string on
        any failure so the conversation is never blocked.

        Args:
            query: Free-text query hint from Hermes (unused for now; future
                   semantic ranking hook).

        Returns:
            Newline-separated memory lines, or "" if nothing to surface.
        """
        try:
            store = self._get_store()
            markers = store.get_recent_markers(
                subject_id=self._subject_id,
                gumi_instance_id=self._gumi_instance_id or None,
                hermes_profile_id=self._hermes_profile_id or None,
                limit=self._max_prefetch,
            )
            lines = []
            for m in markers:
                if self._is_safe_to_surface(m):
                    lines.append(self._format_marker(m))
            return "\n".join(lines)
        except Exception:
            logger.exception("RelicMemoryProvider.prefetch failed — returning empty")
            return ""

    def sync_turn(self, user_msg: str, assistant_msg: str) -> None:
        """Record turn traces without persisting raw content.

        Called by Hermes after each turn. Raw text is hashed; only the
        hash is logged.  No raw content ever reaches the Relic store.

        Args:
            user_msg: Raw user message text (hashed immediately, not stored).
            assistant_msg: Raw assistant response (hashed immediately, not stored).
        """
        try:
            user_hash = _sha256(user_msg)
            assistant_hash = _sha256(assistant_msg)
            logger.debug(
                "sync_turn trace subject=%s user_hash=%s assistant_hash=%s ts=%s",
                self._subject_id,
                user_hash[:12],
                assistant_hash[:12],
                datetime.now(timezone.utc).isoformat(),
            )
            # Raw text is deliberately NOT forwarded to any store.
            # Future: persist PrivacyTrace(content_hash=user_hash) if needed.
        except Exception:
            logger.exception("RelicMemoryProvider.sync_turn failed — ignoring")
