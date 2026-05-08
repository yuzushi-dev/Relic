from relic.gumi_memory.providers.holographic import HolographicCondition


def test_describe_does_not_leak_secrets() -> None:
    desc = HolographicCondition().describe()
    for v in desc.values():
        assert "password" not in str(v).lower()
        assert "api_key" not in str(v).lower()
