from relic.gumi_memory.providers.hindsight import MODE_TOOLS, HindsightCondition


def test_tools_mode_requires_explicit_call() -> None:
    c = HindsightCondition(mode=MODE_TOOLS)
    assert c.explicit_tool_call_required is True
    assert c.runtime_provider is False
