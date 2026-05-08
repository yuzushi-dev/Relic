"""PR16C — ApiServer must reject direct artifact-mutation handlers."""
from __future__ import annotations

import pytest

from relic.ui.api import ApiServer, write_artifact_directly


def test_direct_write_raises() -> None:
    with pytest.raises(PermissionError):
        write_artifact_directly()


def test_no_route_for_unregistered_path() -> None:
    s = ApiServer()
    out = s.call("GET", "/missing", actor_role="researcher")
    assert out["ok"] is False
