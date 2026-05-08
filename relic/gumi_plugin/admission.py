"""Roleplay admission policy (PR22B)."""
from __future__ import annotations

from dataclasses import dataclass

MODE_HIGH_STAKES = "G0"
MODE_RELATIONAL_LIGHT = "G1"
MODE_EXPRESSIVE = "G2"
ADMIT_NEUTRAL_FACTUAL = "neutral_factual_minimal"
ADMIT_RELATIONAL_NORMAL = "relational_normal"
ADMIT_DECLINE = "decline"


@dataclass(frozen=True)
class AdmissionVerdict:
    mode: str
    admission: str
    disclose_when_challenged: bool
    reason: str


class AdmissionPolicy:
    """Default policy gates expressive content behind explicit context."""

    def evaluate(
        self,
        *,
        stakes: str = "low",
        consent: bool = False,
        challenged: bool = False,
        explicit_context: bool = False,
    ) -> AdmissionVerdict:
        if stakes == "high":
            return AdmissionVerdict(
                mode=MODE_HIGH_STAKES,
                admission=ADMIT_NEUTRAL_FACTUAL,
                disclose_when_challenged=True,
                reason="high_stakes_downgrade",
            )
        if not consent:
            return AdmissionVerdict(
                mode=MODE_HIGH_STAKES,
                admission=ADMIT_DECLINE,
                disclose_when_challenged=True,
                reason="no_consent",
            )
        if explicit_context:
            return AdmissionVerdict(
                mode=MODE_EXPRESSIVE,
                admission=ADMIT_RELATIONAL_NORMAL,
                disclose_when_challenged=challenged,
                reason="explicit_context",
            )
        return AdmissionVerdict(
            mode=MODE_RELATIONAL_LIGHT,
            admission=ADMIT_RELATIONAL_NORMAL,
            disclose_when_challenged=challenged or True,
            reason="default_relational_light",
        )
