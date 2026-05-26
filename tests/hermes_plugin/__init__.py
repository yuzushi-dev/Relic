"""Tests for the Relic Hermes plugin."""

from __future__ import annotations

from pathlib import Path
from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)

_PLUGIN_ROOT = Path(__file__).resolve().parents[2] / "hermes-plugin"
if _PLUGIN_ROOT.exists():
    __path__.append(str(_PLUGIN_ROOT))
