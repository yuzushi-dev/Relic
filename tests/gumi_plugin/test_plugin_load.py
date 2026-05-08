"""PR22E — plugin load behavior."""
from __future__ import annotations

from relic.gumi_plugin import GumiPlugin, load_plugin


def test_default_plugin_is_disabled() -> None:
    p = load_plugin(None)
    assert isinstance(p, GumiPlugin)
    assert p.enabled is False
    assert p.is_ready() is False


def test_fail_closed_returns_redacted() -> None:
    p = GumiPlugin()
    fc = p.fail_closed()
    assert fc["context_pack"] is None
    assert fc["redacted"] is True
