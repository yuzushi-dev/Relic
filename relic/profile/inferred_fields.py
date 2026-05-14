"""PR08 — typed InferredField model for system_inferred_fields."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

CLINICAL_TERMS = frozenset({
    "bipolar", "depression", "adhd", "eating disorder", "substance use disorder",
    "chronic pain", "medical condition", "diagnosis", "risk score", "clinical triage",
    "therapy", "medical advice", "clinical", "pathology", "disorder", "syndrome",
    "illness", "disease", "patient", "diagnostic", "psychiatric", "psychological",
})

# Inferred fields default confidence cap — weak evidence
DEFAULT_CONFIDENCE_CAP = 0.35
MULTI_EVIDENCE_CAP = 0.55


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _contains_clinical_term(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    v = value.lower()
    return any(term in v for term in CLINICAL_TERMS)


@dataclass
class InferredField:
    """A single system-inferred field with governance metadata.

    - clinical_interpretation_allowed is always False
    - confidence is capped at DEFAULT_CONFIDENCE_CAP unless multiple evidence refs
    - subject_visible and gumi_visible default False
    - correction_state tracks whether subject has disputed this field
    """
    field_name: str
    value: Any
    confidence: float
    source_refs: list[str] = field(default_factory=list)
    updated_at: str = field(default_factory=_now_iso)
    clinical_interpretation_allowed: bool = False
    subject_visible: bool = False
    gumi_visible: bool = False
    correction_state: str = "active"  # active | corrected | disputed | blocked

    def __post_init__(self) -> None:
        if self.clinical_interpretation_allowed:
            raise ValueError("clinical_interpretation_allowed must always be False")
        if _contains_clinical_term(self.value):
            raise ValueError(
                f"InferredField value contains forbidden clinical term: {self.value!r}"
            )
        # Enforce confidence cap
        cap = MULTI_EVIDENCE_CAP if len(self.source_refs) >= 2 else DEFAULT_CONFIDENCE_CAP
        if self.confidence > cap:
            self.confidence = cap

    def apply_correction(self) -> "InferredField":
        """Mark field as corrected by subject — blocks further update loop use."""
        return InferredField(
            field_name=self.field_name,
            value=None,
            confidence=0.0,
            source_refs=self.source_refs,
            updated_at=_now_iso(),
            correction_state="corrected",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_name": self.field_name,
            "value": self.value,
            "confidence": self.confidence,
            "source_refs": self.source_refs,
            "updated_at": self.updated_at,
            "clinical_interpretation_allowed": self.clinical_interpretation_allowed,
            "subject_visible": self.subject_visible,
            "gumi_visible": self.gumi_visible,
            "correction_state": self.correction_state,
        }


def validate_inferred_field_value(value: Any) -> None:
    """Raise ValueError if value contains forbidden clinical terms."""
    if _contains_clinical_term(value):
        raise ValueError(f"Forbidden clinical term in inferred field value: {value!r}")
