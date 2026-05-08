"""conftest for shared-continuity tests."""

import sys
from pathlib import Path

# Use pytest_sessionstart to modify sys.path AFTER conftest is loaded
# but BEFORE test collection begins
def pytest_sessionstart(session):
    _REPO_ROOT = str(Path(__file__).parent.parent.parent)
    # Ensure repo root is at front of sys.path so the hermes_plugin wrapper resolves.
    if _REPO_ROOT in sys.path:
        sys.path.remove(_REPO_ROOT)
    sys.path.insert(0, _REPO_ROOT)
