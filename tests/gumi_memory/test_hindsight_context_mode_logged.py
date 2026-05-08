from relic.gumi_memory.providers.hindsight import MODE_CONTEXT, HindsightCondition


def test_context_mode_must_log_injection() -> None:
    c = HindsightCondition(mode=MODE_CONTEXT)
    assert c.context_injection_logged is True
