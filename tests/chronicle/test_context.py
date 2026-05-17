"""Tests for relic.chronicle.context — T011."""
from __future__ import annotations

import asyncio
import threading
import uuid

import pytest

from relic.chronicle import context as pctx


class TestTraceId:
    def test_new_trace_id_returns_uuid(self) -> None:
        tid = pctx.new_trace_id()
        assert isinstance(tid, uuid.UUID)

    def test_set_and_get_trace_id(self) -> None:
        tid = uuid.uuid4()
        pctx.set_trace_id(tid)
        assert pctx.get_trace_id() == tid

    def test_get_trace_id_none_when_unset(self) -> None:
        pctx._trace_id_var.set(None)
        assert pctx.get_trace_id() is None

    def test_trace_id_unique_per_call(self) -> None:
        ids = [pctx.new_trace_id() for _ in range(100)]
        assert len(set(ids)) == 100


class TestSession:
    def test_register_and_get_session(self) -> None:
        sid = uuid.uuid4()
        pctx.register_session(sid)
        assert pctx.get_session_id() == sid

    def test_get_session_none_when_unset(self) -> None:
        pctx._session_id_var.set(None)
        assert pctx.get_session_id() is None


class TestRun:
    def test_register_and_get_run(self) -> None:
        rid = uuid.uuid4()
        pctx.register_run(rid)
        assert pctx.get_run_id() == rid

    def test_get_run_none_when_unset(self) -> None:
        pctx._run_id_var.set(None)
        assert pctx.get_run_id() is None


class TestExperiment:
    def test_register_and_get_experiment(self) -> None:
        eid = uuid.uuid4()
        pctx.register_experiment(eid)
        assert pctx.get_experiment_id() == eid

    def test_get_experiment_none_when_unset(self) -> None:
        pctx._experiment_id_var.set(None)
        assert pctx.get_experiment_id() is None


class TestSpanId:
    def test_new_span_id_returns_uuid(self) -> None:
        sid = pctx.new_span_id()
        assert isinstance(sid, uuid.UUID)

    def test_new_span_id_unique(self) -> None:
        ids = [pctx.new_span_id() for _ in range(50)]
        assert len(set(ids)) == 50

    def test_set_and_get_span_id(self) -> None:
        sid = uuid.uuid4()
        pctx.set_span_id(sid)
        assert pctx.get_span_id() == sid


class TestTraceContext:
    def test_make_traceparent_basic(self) -> None:
        trace = uuid.UUID("0123456789abcdef0123456789abcdef")
        parent = uuid.UUID("fedcba9876543210fedcba9876543210")
        tp = pctx.make_traceparent(trace, parent, trace_flags=1)
        parts = tp.split("-")
        assert len(parts) == 4
        assert parts[0] == "00"  # version
        assert parts[1] == "0123456789ABCDEF0123456789ABCDEF"  # 32 hex uppercase
        assert parts[2] == "FEDCBA9876543210"  # 16 hex uppercase
        assert parts[3] == "01"  # sampled

    def test_make_traceparent_no_parent_generates_span(self) -> None:
        trace = uuid.uuid4()
        tp = pctx.make_traceparent(trace, None, trace_flags=0)
        parts = tp.split("-")
        assert len(parts[2]) == 16  # 16 hex chars
        assert parts[3] == "00"
        assert parts[1] == trace.hex.upper()

    def test_make_traceparent_uppercase_hex(self) -> None:
        trace = uuid.UUID("abcdef0123456789abcdef0123456789")
        parent = uuid.UUID("1234567890abcdef1234567890abcdef")
        tp = pctx.make_traceparent(trace, parent)
        _, trace_hex, parent_hex, flags_hex = tp.split("-")
        assert trace_hex == "ABCDEF0123456789ABCDEF0123456789"
        assert parent_hex == "1234567890ABCDEF"
        assert flags_hex == "01"

    def test_get_traceparent_returns_none_when_no_trace(self) -> None:
        pctx._trace_id_var.set(None)
        pctx._span_id_var.set(None)
        assert pctx.get_traceparent() is None

    def test_get_traceparent_with_trace_and_span(self) -> None:
        trace = uuid.uuid4()
        span = uuid.uuid4()
        pctx.set_trace_id(trace)
        pctx.set_span_id(span)
        tp = pctx.get_traceparent()
        assert tp is not None
        assert tp.startswith(f"00-{trace.hex.upper()}-")
        _, trace_hex, parent_hex, flags_hex = tp.split("-")
        assert len(trace_hex) == 32
        assert len(parent_hex) == 16
        assert len(flags_hex) == 2


class TestCrossThreadIsolation:
    def test_trace_id_isolated_between_threads(self) -> None:
        results: dict[str, uuid.UUID | None] = {}
        tid = uuid.uuid4()
        pctx.set_trace_id(tid)

        def worker() -> None:
            # Each thread starts with no trace_id (contextvars don't propagate)
            results["saw"] = pctx.get_trace_id()
            pctx.set_trace_id(uuid.uuid4())
            results["set"] = pctx.get_trace_id()

        t = threading.Thread(target=worker)
        t.start()
        t.join()

        # Main thread still has original tid
        assert pctx.get_trace_id() == tid
        # Worker saw None (isolated context)
        assert results["saw"] is None


class TestCrossAsyncIsolation:
    def test_trace_id_isolated_between_tasks(self) -> None:
        results: list[uuid.UUID | None] = []
        main_tid = uuid.uuid4()
        pctx.set_trace_id(main_tid)

        async def task_a() -> None:
            # Inherits context from parent
            results.append(pctx.get_trace_id())
            # Modify is local to this task
            pctx.set_trace_id(uuid.uuid4())
            results.append(pctx.get_trace_id())

        async def task_b() -> None:
            await asyncio.sleep(0)  # yield to ensure task_a sets its own tid
            results.append(pctx.get_trace_id())

        async def main() -> None:
            # Reset before test
            pctx._trace_id_var.set(main_tid)
            await asyncio.gather(task_a(), task_b())

        asyncio.run(main())

        # Main context still has main_tid
        assert pctx.get_trace_id() == main_tid
        # task_a saw main_tid initially then changed to its own
        assert results[0] == main_tid
        assert results[1] != main_tid
        # task_b saw main_tid (inherited from main)
        assert results[2] == main_tid


class TestCopyContextTokens:
    def test_copy_and_restore_tokens(self) -> None:
        tid = uuid.uuid4()
        sid = uuid.uuid4()
        rid = uuid.uuid4()
        eid = uuid.uuid4()
        spid = uuid.uuid4()

        pctx.set_trace_id(tid)
        pctx.register_session(sid)
        pctx.register_run(rid)
        pctx.register_experiment(eid)
        pctx.set_span_id(spid)

        tokens = pctx.copy_context_tokens()
        assert tokens["trace_id"] == tid
        assert tokens["session_id"] == sid
        assert tokens["run_id"] == rid
        assert tokens["experiment_id"] == eid
        assert tokens["span_id"] == spid

        # Clear and restore
        pctx.reset_context()
        assert pctx.get_trace_id() is None

        pctx.set_context_tokens(tokens)
        assert pctx.get_trace_id() == tid
        assert pctx.get_session_id() == sid


class TestResetContext:
    def test_reset_clears_all_vars(self) -> None:
        pctx.set_trace_id(uuid.uuid4())
        pctx.register_session(uuid.uuid4())
        pctx.register_run(uuid.uuid4())
        pctx.register_experiment(uuid.uuid4())
        pctx.set_span_id(uuid.uuid4())

        pctx.reset_context()

        assert pctx.get_trace_id() is None
        assert pctx.get_session_id() is None
        assert pctx.get_run_id() is None
        assert pctx.get_experiment_id() is None
        assert pctx.get_span_id() is None
