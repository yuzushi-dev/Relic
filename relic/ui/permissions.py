"""Permission matrix for the Researcher UI (PR16C / TOOL_PERMISSION_MATRIX.md)."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Permission(str, Enum):
    READ_QUEUE = "read_queue"
    READ_ARTIFACT = "read_artifact"
    READ_STUDY_OVERVIEW = "read_study_overview"
    EMIT_FEEDBACK = "emit_feedback"
    REQUEST_RECOMPILE = "request_recompile"
    EXPORT_BUNDLE = "export_bundle"
    REPLAY_TRACE = "replay_trace"


DEFAULT_MATRIX: dict[str, set[Permission]] = {
    "researcher": {
        Permission.READ_QUEUE,
        Permission.READ_ARTIFACT,
        Permission.READ_STUDY_OVERVIEW,
        Permission.EMIT_FEEDBACK,
        Permission.REQUEST_RECOMPILE,
        Permission.REPLAY_TRACE,
    },
    "subject": {
        Permission.READ_ARTIFACT,
        Permission.EMIT_FEEDBACK,
    },
    "viewer": {
        Permission.READ_QUEUE,
        Permission.READ_ARTIFACT,
    },
}


@dataclass
class PermissionMatrix:
    grants: dict[str, set[Permission]] = field(default_factory=dict)

    @classmethod
    def default(cls) -> "PermissionMatrix":
        return cls(grants={r: set(p) for r, p in DEFAULT_MATRIX.items()})

    def can(self, role: str, perm: Permission) -> bool:
        return perm in self.grants.get(role, set())


def require_permission(matrix: PermissionMatrix, role: str, perm: Permission) -> None:
    if not matrix.can(role, perm):
        raise PermissionError(f"role={role!r} lacks {perm.value!r}")
