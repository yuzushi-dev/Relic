from relic.gumi_memory.providers.honcho import HonchoCondition


def test_honcho_outputs_candidates_only() -> None:
    c = HonchoCondition()
    assert c.outputs_are_candidates_only is True
    assert c.runtime_provider is False
