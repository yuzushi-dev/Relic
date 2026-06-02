"""PR22E, plugin load behavior."""
from __future__ import annotations

from relic.gumi_plugin import GumiPlugin, load_plugin


def test_default_plugin_is_disabled() -> None:
    p = load_plugin(None)
    assert isinstance(p, GumiPlugin)
    assert p.enabled is False
    assert p.is_ready() is False


def test_fail_closed_returns_none() -> None:
    p = GumiPlugin()
    fc = p.fail_closed()
    assert fc is None  # Hermes contract: fail-closed returns None, never an error dict
