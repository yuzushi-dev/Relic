"""Context variables for distributed tracing propagation (T011).

Uses Python's contextvars (3.7+) for thread-safe, async-native
trace context management across coroutines and threads.
"""
from __future__ import annotations

from contextvars import ContextVar
from typing import TypedDict
from uuid import UUID, uuid4

__all__ = [
    "get_trace_id",
    "new_trace_id",
    "set_trace_id",
    "get_session_id",
    "register_session",
    "get_run_id",
    "register_run",
    "get_experiment_id",
    "register_experiment",
    "get_span_id",
    "new_span_id",
    "set_span_id",
    "get_traceparent",
    "make_traceparent",
    "copy_context_tokens",
    "set_context_tokens",
    "reset_context",
    # exposed for conftest fixture
    "_trace_id_var",
    "_session_id_var",
    "_run_id_var",
    "_experiment_id_var",
    "_span_id_var",
    "_parent_id_var",
    # aliases matching conftest expectations
    "_trace_id",
    "_session_id",
    "_run_id",
    "_experiment_id",
]

# ── Context variables ────────────────────────────────────────────────────────

_trace_id_var: ContextVar[UUID | None] = ContextVar("trace_id", default=None)
_session_id_var: ContextVar[UUID | None] = ContextVar("session_id", default=None)
_run_id_var: ContextVar[UUID | None] = ContextVar("run_id", default=None)
_experiment_id_var: ContextVar[UUID | None] = ContextVar("experiment_id", default=None)
_span_id_var: ContextVar[UUID | None] = ContextVar("span_id", default=None)
_parent_id_var: ContextVar[UUID | None] = ContextVar("parent_id", default=None)

# Aliases used by conftest fixture (clean_contextvars)
_trace_id = _trace_id_var
_session_id = _session_id_var
_run_id = _run_id_var
_experiment_id = _experiment_id_var


# ── Context tokens (snapshot/restore) ────────────────────────────────────────

class ContextTokens(TypedDict):
    trace_id: UUID | None
    session_id: UUID | None
    run_id: UUID | None
    experiment_id: UUID | None
    span_id: UUID | None


def copy_context_tokens() -> ContextTokens:
    """Snapshot current context values as a dict (for later restore)."""
    return ContextTokens(
        trace_id=_trace_id_var.get(),
        session_id=_session_id_var.get(),
        run_id=_run_id_var.get(),
        experiment_id=_experiment_id_var.get(),
        span_id=_span_id_var.get(),
    )


def set_context_tokens(tokens: ContextTokens) -> None:
    """Restore context from a previously captured tokens snapshot."""
    _trace_id_var.set(tokens["trace_id"])
    _session_id_var.set(tokens["session_id"])
    _run_id_var.set(tokens["run_id"])
    _experiment_id_var.set(tokens["experiment_id"])
    _span_id_var.set(tokens["span_id"])


def reset_context() -> None:
    """Reset all trace context variables to None."""
    _trace_id_var.set(None)
    _session_id_var.set(None)
    _run_id_var.set(None)
    _experiment_id_var.set(None)
    _span_id_var.set(None)


# ── trace_id ────────────────────────────────────────────────────────────────

def get_trace_id() -> UUID | None:
    """Return the current trace_id from context, or None if not set."""
    return _trace_id_var.get()


def new_trace_id() -> UUID:
    """Generate and set a new trace_id, returning it."""
    tid = uuid4()
    _trace_id_var.set(tid)
    return tid


def set_trace_id(trace_id: UUID) -> None:
    """Set the current trace_id in context."""
    _trace_id_var.set(trace_id)


# ── session_id ───────────────────────────────────────────────────────────────

def get_session_id() -> UUID | None:
    """Return the current session_id from context, or None if not set."""
    return _session_id_var.get()


def register_session(session_id: UUID) -> None:
    """Register the session_id in context."""
    _session_id_var.set(session_id)


# ── run_id ───────────────────────────────────────────────────────────────────

def get_run_id() -> UUID | None:
    """Return the current run_id from context, or None if not set."""
    return _run_id_var.get()


def register_run(run_id: UUID) -> None:
    """Register the run_id in context."""
    _run_id_var.set(run_id)


# ── experiment_id ────────────────────────────────────────────────────────────

def get_experiment_id() -> UUID | None:
    """Return the current experiment_id from context, or None if not set."""
    return _experiment_id_var.get()


def register_experiment(experiment_id: UUID) -> None:
    """Register the experiment_id in context."""
    _experiment_id_var.set(experiment_id)


# ── span_id ────────────────────────────────────────────────────────────────

def get_span_id() -> UUID | None:
    """Return the current span_id from context, or None if not set."""
    return _span_id_var.get()


def new_span_id() -> UUID:
    """Generate and set a new span_id, returning it."""
    sid = uuid4()
    _span_id_var.set(sid)
    return sid


def set_span_id(span_id: UUID) -> None:
    """Set the current span_id in context."""
    _span_id_var.set(span_id)


# ── W3C Trace Context ────────────────────────────────────────────────────────

def _uuid_to_span_hex(uuid_val: UUID | None) -> str:
    """Convert a UUID to 16 uppercase hex chars for span_id field."""
    if uuid_val is None:
        # Generate a fresh random span ID
        return uuid4().hex[:16].upper()
    # Use last 16 chars (last 64 bits) of the UUID as the span
    return uuid_val.hex.upper()[-16:]


def get_traceparent() -> str | None:
    """Return W3C Trace Context traceparent header value.

    Returns None if no trace_id is set.
    Format: version-traceId-parentId-traceFlags
      version   : 2 hex chars (00)
      traceId   : 32 hex chars (128-bit UUID without dashes, uppercase)
      parentId  : 16 hex chars (64-bit span ID, uppercase)
      traceFlags: 2 hex chars (01 = sampled)
    """
    trace_id = _trace_id_var.get()
    if trace_id is None:
        return None
    parent_id = _span_id_var.get()
    return make_traceparent(trace_id, parent_id)


def make_traceparent(
    trace_id: UUID,
    parent_id: UUID | None,
    trace_flags: int = 1,
) -> str:
    """Build a W3C Trace Context traceparent string.

    Args:
        trace_id   : 128-bit trace identifier
        parent_id  : Optional 64-bit parent/span identifier
        trace_flags: Trace flags byte (default 1 = sampled)

    Returns:
        W3C traceparent string: version(2)-traceId(32)-parentId(16)-flags(2)
    """
    trace_hex = trace_id.hex.upper()  # 32 uppercase chars
    flags_hex = f"{trace_flags:02X}"
    parent_hex = _uuid_to_span_hex(parent_id)
    return f"00-{trace_hex}-{parent_hex}-{flags_hex}"
