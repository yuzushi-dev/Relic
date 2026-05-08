"""CLI pytest configuration.

The CLI tests mutate process-level state and generate executable scripts that
spawn Python subprocesses. Keep them serial even when the outer pytest command
uses xdist or another parallel runner.
"""

from __future__ import annotations

import fcntl
from pathlib import Path
from typing import Iterator

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "xdist_group(name): run marked tests in the same xdist worker when xdist is active",
    )


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        item.add_marker(pytest.mark.xdist_group("cli"))


@pytest.fixture(autouse=True)
def _serialize_cli_tests(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    lock_path = tmp_path_factory.getbasetemp().parent / "relic_cli_tests.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("w", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
