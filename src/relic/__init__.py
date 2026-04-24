"""Relic runtime package."""
import os as _os
import sys as _sys
import pathlib as _pathlib


def _bridge_brand_env() -> None:
    """Allow Relic-branded env vars to drive the legacy runtime."""
    for key, value in tuple(_os.environ.items()):
        if not key.startswith("RELIC_"):
            continue
        legacy_key = f"RELIC_{key[6:]}"
        _os.environ.setdefault(legacy_key, value)


_bridge_brand_env()

# Modules in this package use bare imports (e.g. `from relic_db import ...`)
# that were originally written to run as standalone scripts from this directory.
# Adding the package directory to sys.path preserves that behaviour when the
# package is imported as `relic.*`.
_pkg_dir = str(_pathlib.Path(__file__).parent)
if _pkg_dir not in _sys.path:
    _sys.path.insert(0, _pkg_dir)
