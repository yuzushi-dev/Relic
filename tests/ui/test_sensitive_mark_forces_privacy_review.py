"""PR16C — permission matrix denies subject role from request_recompile."""
from __future__ import annotations

import pytest

from relic.ui.permissions import (
    Permission,
    PermissionMatrix,
    require_permission,
)


def test_subject_cannot_request_recompile() -> None:
    m = PermissionMatrix.default()
    with pytest.raises(PermissionError):
        require_permission(m, "subject", Permission.REQUEST_RECOMPILE)


def test_researcher_can_replay() -> None:
    m = PermissionMatrix.default()
    require_permission(m, "researcher", Permission.REPLAY_TRACE)  # no raise
