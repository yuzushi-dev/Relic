"""Core-facing database exports."""

from __future__ import annotations

import sqlite3

from mnemon.relic_db import *  # noqa: F401,F403

# Compatibility symbol for the extracted core package tests and future typing.
RelicDB = sqlite3.Connection

