""""Researcher UI HTTP API surface (PR16C).

The API is read-mostly: every write must flow through the feedback processor
(see `relic.ui.feedback`). Direct artifact mutation is forbidden.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from relic.ui.permissions import (
    Permission,
    PermissionMatrix,
    require_permission,
)


@dataclass
class ApiRoute:
    method: str
    path: str
    permission: Permission
    handler: Callable[..., Any]


@dataclass
class ApiServer:
    matrix: PermissionMatrix = field(default_factory=PermissionMatrix.default)
    routes: list[ApiRoute] = field(default_factory=list)

    def register(
        self,
        method: str,
        path: str,
        permission: Permission,
        handler: Callable[..., Any],
    ) -> None:
        self.routes.append(ApiRoute(method, path, permission, handler))

    def call(
        self,
        method: str,
        path: str,
        *,
        actor_role: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        for r in self.routes:
            if r.method.upper() == method.upper() and r.path == path:
                require_permission(self.matrix, actor_role, r.permission)
                return {"ok": True, "result": r.handler(payload or {})}
        return {"ok": False, "error": "route_not_found"}


def write_artifact_directly(*_args: Any, **_kw: Any) -> None:
    """Invariant: PR16C forbids direct artifact mutation from the UI.

    This stub exists so tests can assert the symbol is never wired into
    `ApiServer.routes`.
    """
    raise PermissionError("Direct artifact writes are forbidden by PR16C")


@dataclass
class UIBackend:
    """HTTP-style handlers backed by fixture data.

    All methods are read-only: no artifact writes (PR16C).
    """

    _fixture_path: Path = field(default_factory=lambda: Path("fixtures/researcher-workbench/study_overview.json"))

    def _load_overview(self) -> dict[str, Any]:
        """Load raw overview fixture from disk."""
        # Try workspace fixture path first, fall back to package resource
        candidates = [
            Path("fixtures/researcher-workbench/study_overview.json"),
            Path(__file__).parent.parent.parent / "fixtures" / "researcher-workbench" / "study_overview.json",
        ]
        for p in candidates:
            if p.exists():
                return json.loads(p.read_text(encoding="utf-8"))
        # Fallback: use package data (installed relic)
        import relic.ui
        pkg_root = Path(relic.ui.__file__).parent.parent.parent
        pkg_fixture = pkg_root / "fixtures" / "researcher-workbench" / "study_overview.json"
        if pkg_fixture.exists():
            return json.loads(pkg_fixture.read_text(encoding="utf-8"))
        raise FileNotFoundError(f"study_overview.json not found in any of: {candidates}")

    def get_study_overview(self, _: dict[str, Any]) -> dict[str, Any]:
        """GET /api/study/overview - aggregate study summary.

        Returns study-level counters and risk/status aggregates.
        Subject registry is excluded (not exposed at aggregate level).
        """
        data = self._load_overview()
        # Strip subject_registry - only expose pre-aggregated fields
        overview = {k: v for k, v in data.items() if k != "subject_registry"}
        return overview

    def get_subjects(self, _: dict[str, Any]) -> dict[str, Any]:
        """GET /api/study/subjects - full subject registry.

        Returns the raw subject_registry list from the fixture.
        """
        data = self._load_overview()
        return {"subjects": data.get("subject_registry", [])}


def create_study_api() -> ApiServer:
    """Factory: build a fully-wired ApiServer with Study Dashboard routes."""
    backend = UIBackend()
    server = ApiServer()

    server.register(
        "GET",
        "/api/study/overview",
        Permission.READ_STUDY_OVERVIEW,
        backend.get_study_overview,
    )
    server.register(
        "GET",
        "/api/study/subjects",
        Permission.READ_STUDY_OVERVIEW,
        backend.get_subjects,
    )

    return server
