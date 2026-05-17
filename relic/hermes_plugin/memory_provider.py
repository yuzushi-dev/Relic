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

try:
    from relic.chronicle import emit_event, EventCategory
    _CHRONICLE = True
except Exception:
    _CHRONICLE = False
    EventCategory = None  # type: ignore

_REDACTED = "[redacted]"


_SHA256_CAP = 65536  # 64 KiB — trace identity only, no need to hash full blobs


def _sha256(text: str) -> str:
    return hashlib.sha256(text[:_SHA256_CAP].encode()).hexdigest()


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
        relic_home: str | None = None,
    ) -> None:
        # Hard guard: a provider without a subject_id would silently serve the
        # wrong subject's markers to any Hermes profile that registers it.
        if not subject_id or not subject_id.strip():
            raise ValueError(
                "RelicMemoryProvider requires a non-empty subject_id. "
                "Each Hermes profile must register its own provider instance."
            )
        self._subject_id = subject_id
        self._gumi_instance_id = gumi_instance_id or ""
        self._hermes_profile_id = hermes_profile_id or ""
        self._max_prefetch = max_prefetch
        import os as _os
        self._relic_home = relic_home or _os.environ.get("RELIC_HOME") or None
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
        """Convert a continuity marker to a compact human-readable line.

        Returns an empty string when the marker has no surfaceable content.
        Callers must filter empty lines — never inject placeholder noise into
        the LLM context.
        """
        words = marker.get("subject_words") or marker.get("words") or []
        if isinstance(words, list):
            text = " ".join(str(w) for w in words)
        else:
            text = str(words)
        return text.strip()

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
                if not self._is_safe_to_surface(m):
                    continue
                line = self._format_marker(m)
                if line:  # drop empty markers — never inject placeholder noise
                    lines.append(line)
            if lines and _CHRONICLE:
                try:
                    emit_event(
                        event_type="memory_prefetched",
                        event_category=EventCategory.MEMORY,
                        source_module="relic.hermes_plugin.memory_provider",
                        subject_id=self._subject_id,
                        profile_id=self._hermes_profile_id or None,
                        hermes_profile_id=self._hermes_profile_id or None,
                        payload={
                            "marker_count": len(lines),
                            "max_prefetch": self._max_prefetch,
                        },
                    )
                except Exception:
                    pass  # fail-open: never block prefetch on emit failure
            return "\n".join(lines)
        except Exception:
            logger.exception("RelicMemoryProvider.prefetch failed — returning empty")
            return ""

    def sync_turn(self, user_msg: str, assistant_msg: str) -> None:
        """Record turn traces without persisting raw content.

        Called by Hermes after each turn. Raw text is hashed; only the
        hash is logged.  No raw content ever reaches the Relic store.

        Exception: if consent_for_active_elicitation is True in the subject's
        delivery_policy.json, the user message is checked against pending
        checkin exchanges within the capture time window and, if one is found,
        written to relic.db as reply_text.  This is a specific carve-out: text
        goes only to the subject's own longitudinal store, not to Hermes memory.

        Args:
            user_msg: Raw user message text (hashed immediately, not stored
                      in Hermes memory; may be captured in relic.db per above).
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
            # Capture checkin reply — consent-gated carve-out to relic.db only.
            try:
                from relic.checkin.reply_capture import capture_reply_if_pending
                capture_reply_if_pending(user_msg, self._subject_id, relic_home=self._relic_home)
            except Exception:
                pass  # fail-open: never block sync_turn on capture error
        except Exception:
            logger.exception("RelicMemoryProvider.sync_turn failed — ignoring")
