"""PR22E — pre_llm_call hook dispatch."""
from __future__ import annotations

from relic.gumi_plugin import hooks


def setup_function() -> None:
    hooks.reset()


def test_dispatch_with_no_handlers_returns_empty() -> None:
    assert hooks.dispatch(hooks.PRE_LLM_CALL, {"prompt": "hi"}) == []


def test_handler_receives_payload() -> None:
    seen = []

    def h(p):
        seen.append(p)
        return {"context_pack": {}}

    hooks.register(hooks.PRE_LLM_CALL, h)
    out = hooks.dispatch(hooks.PRE_LLM_CALL, {"prompt": "hi"})
    assert seen == [{"prompt": "hi"}]
    assert out and "context_pack" in out[0]


def test_handler_exception_is_fail_closed() -> None:
    def boom(_p):
        raise RuntimeError("bad")

    hooks.register(hooks.PRE_LLM_CALL, boom)
    out = hooks.dispatch(hooks.PRE_LLM_CALL, {})
    # Hermes contract: exception → None in output, never an error dict
    assert out == [None]
