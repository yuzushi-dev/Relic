"""PR22E, plugin must not inject context when not ready."""
from __future__ import annotations

from relic.gumi_plugin import GumiPlugin


def test_unready_plugin_fails_closed() -> None:
    p = GumiPlugin(enabled=False)
    assert p.is_ready() is False
    fc = p.fail_closed()
    assert fc is None  # Hermes contract: fail-closed returns None, never an error dict


def test_ready_requires_config() -> None:
    p = GumiPlugin(enabled=True, config={})
    assert p.is_ready() is False
