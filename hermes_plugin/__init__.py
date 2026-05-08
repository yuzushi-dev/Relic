"""Portable import wrapper for the Hermes plugin source tree.

The implementation lives in ``hermes-plugin/`` because Hermes discovers that
directory as a plugin bundle. Python imports cannot use hyphens in module names,
so this package exposes the same tree as ``hermes_plugin`` without relying on a
machine-local symlink.
"""

from __future__ import annotations

from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "hermes-plugin"
__path__ = [str(_PLUGIN_ROOT)]
