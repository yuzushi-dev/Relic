from relic.gumi_memory.providers.byterover import ByteRoverCondition


def test_byterover_is_operational_only() -> None:
    c = ByteRoverCondition()
    assert c.operational_only is True
    assert c.relational_truth is False
    assert c.runtime_provider is False
