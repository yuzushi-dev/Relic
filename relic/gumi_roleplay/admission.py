"""PR04, RoleplayAdmissionController and RoleplayAdmissionEvent.

Thin wrapper over AdmissionPolicy that:
- Accepts structured task_type / sensitivity / cac_decisions inputs
- Returns a RoleplayAdmissionEvent linked to pack_id for audit
- Never stores persistent state; only ephemeral per-turn decisions
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from relic.gumi_plugin.admission import AdmissionPolicy, AdmissionVerdict


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# Task-type → stakes mapping (drives G0/G1/G2 selection)
_HIGH_STAKES_TASK_TYPES = frozenset({
    "legal", "medical", "financial", "crisis", "high_stakes",
})

_RELATIONAL_TASK_TYPES = frozenset({
    "relational", "reflective", "creative", "emotional",
})


@dataclass
class RoleplayAdmissionEvent:
    """Per-turn admission decision record linked to a PCP pack_id."""

    event_id: str = field(default_factory=lambda: f"RAE-{uuid4().hex[:8]}")
    pack_id: str | None = None
    session_id: str | None = None

    roleplay_level: str = "off"          # G0/G1/G2 or off/minimal/light/normal/high
    continuity_mode: str = "none"
    disclosure_required: bool = True

    reasons: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "pack_id": self.pack_id,
            "session_id": self.session_id,
            "roleplay_level": self.roleplay_level,
            "continuity_mode": self.continuity_mode,
            "disclosure_required": self.disclosure_required,
            "reasons": self.reasons,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }


class RoleplayAdmissionController:
    """Decide roleplay level and continuity mode for a given turn.

    Input signals:
    - task_type: str, classified task (technical, relational, medical, …)
    - sensitivity: str, "low" | "medium" | "high"
    - consent: bool, user has explicitly opted in to relational mode
    - challenged: bool, user is questioning Gumi's nature
    - cac_decisions: list[dict], CAC decision summaries (optional)
    - continuity_candidates: list[dict], admitted continuity markers (optional)

    Returns RoleplayAdmissionEvent with final roleplay_level and continuity_mode.
    """

    def __init__(self) -> None:
        self._policy = AdmissionPolicy()

    def evaluate(
        self,
        *,
        task_type: str = "technical",
        sensitivity: str = "low",
        consent: bool = False,
        challenged: bool = False,
        pack_id: str | None = None,
        session_id: str | None = None,
        cac_decisions: list[dict] | None = None,
        continuity_candidates: list[dict] | None = None,
        disable_roleplay: bool = False,
    ) -> RoleplayAdmissionEvent:
        task_lower = task_type.lower()
        stakes = "high" if (task_lower in _HIGH_STAKES_TASK_TYPES or sensitivity == "high") else "low"

        # Override: /disable_roleplay command or explicit flag
        if disable_roleplay:
            return RoleplayAdmissionEvent(
                pack_id=pack_id,
                session_id=session_id,
                roleplay_level="off",
                continuity_mode="none",
                disclosure_required=True,
                reasons=["disable_roleplay_command"],
            )

        verdict: AdmissionVerdict = self._policy.evaluate(
            stakes=stakes,
            consent=consent,
            challenged=challenged,
            explicit_context=task_lower in _RELATIONAL_TASK_TYPES,
        )

        roleplay_level = _verdict_to_level(verdict)
        continuity_mode = _decide_continuity(
            roleplay_level, continuity_candidates or []
        )

        return RoleplayAdmissionEvent(
            pack_id=pack_id,
            session_id=session_id,
            roleplay_level=roleplay_level,
            continuity_mode=continuity_mode,
            disclosure_required=verdict.disclose_when_challenged,
            reasons=[verdict.reason],
            metadata={
                "task_type": task_type,
                "sensitivity": sensitivity,
                "stakes": stakes,
                "cac_decision_count": len(cac_decisions or []),
                "continuity_candidate_count": len(continuity_candidates or []),
            },
        )


def _verdict_to_level(v: AdmissionVerdict) -> str:
    mode_map = {
        "G0": "off",
        "G1": "light",
        "G2": "normal",
    }
    return mode_map.get(v.mode, "off")


def _decide_continuity(roleplay_level: str, candidates: list[dict]) -> str:
    if roleplay_level == "off":
        return "none"
    if not candidates:
        return "none"
    if roleplay_level == "light":
        return "compact"
    return "expanded"
