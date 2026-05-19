"""Suppress background_review_callback on messaging platform agents.

The Hermes gateway wires agent.background_review_callback to send
"💾 Self-improvement review: ..." messages to the subject's chat after
every turn. This is a TUI-only debug signal that leaks into Telegram,
Signal, and other subject-facing platforms.

This module monkey-patches RunAgent so that background_review_callback
is always a no-op, regardless of what gateway/run.py assigns. Applied
once at import time; survives Hermes core updates.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_patched = False


def apply() -> None:
    """Patch RunAgent.background_review_callback to a no-op property.

    Idempotent — safe to call multiple times.
    """
    global _patched
    if _patched:
        return
    try:
        from run_agent import RunAgent  # Hermes internal module

        if isinstance(getattr(RunAgent, "background_review_callback", None), property):
            # Already a property (e.g. future Hermes version added the flag)
            logger.debug("review_suppressor: already a property, skip patch")
            _patched = True
            return

        # Replace the plain attribute slot with a no-op property so that
        # gateway/run.py's `agent.background_review_callback = _bg_review_send`
        # silently discards the callback.
        RunAgent.background_review_callback = property(  # type: ignore[attr-defined]
            fget=lambda self: None,
            fset=lambda self, _: None,
        )
        _patched = True
        logger.debug("review_suppressor: RunAgent.background_review_callback patched to no-op")
    except Exception as exc:
        logger.warning("review_suppressor: patch failed, background review may appear in chat: %s", exc)
