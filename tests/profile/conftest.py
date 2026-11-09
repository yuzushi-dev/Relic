"""Profile tests must never reach a real Hermes install.

The registry looks the binary up with ``shutil.which("hermes")`` and then creates,
lists and deletes profiles with it. On a developer machine that finds the real one, so
it is hidden here; tests that need a Hermes stub install their own.
"""
from __future__ import annotations

import shutil

import pytest


@pytest.fixture(autouse=True)
def _hide_real_hermes(monkeypatch: pytest.MonkeyPatch) -> None:
    real_which = shutil.which
    monkeypatch.setattr(
        shutil,
        "which",
        lambda cmd, *args, **kwargs: None if cmd == "hermes" else real_which(cmd, *args, **kwargs),
    )
