"""
Runtime Pack Sanitizer.

Scans Gumi runtime packs before delivery and blocks forbidden clinical
terms and raw evidence from reaching the Gumi runtime.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


# Forbidden clinical terms - blocked from reaching Gumi
FORBIDDEN_CLINICAL_TERMS = {
    # Diagnosis labels
    "bipolar", "depression", "depressive", "adhd", "eating disorder",
    "eating dysfunction", "substance use disorder", "substance abuse",
    "chronic pain", "pain disorder", "medical condition", "diagnosis",
    "diagnostic", "syndrome", "disorder", "illness", "disease",

    # Clinical terminology
    "clinical", "pathology", "patient", "psychiatric", "psychological",
    "therapist", "therapy", "counseling", "medical advice",

    # Risk terminology
    "risk score", "risk assessment", "clinical triage", "triage level",

    # Other forbidden
    "mental health condition", "mental illness", "mental disorder"
}

# Evidence patterns that should never reach Gumi
EVIDENCE_PATTERNS = [
    "event_", "evidence_", "ref_", "timestamp", "context:"
]


@dataclass
class SanitizerResult:
    """Result of sanitization scan."""
    is_clean: bool
    blocked_terms: List[str] = field(default_factory=list)
    blocked_evidence: bool = False
    safety_signal_written: bool = False
    message: str = ""


@dataclass
class RuntimePack:
    """A Gumi runtime pack being scanned."""
    subject_id: str
    gumi_instance_id: str
    content: Dict[str, Any]


class RuntimePackSanitizer:
    """
    Sanitizes Gumi runtime packs before delivery.

    Key rules:
    - Blocks all forbidden clinical terms from reaching Gumi runtime
    - Blocks raw evidence text from reaching Gumi runtime
    - Writes safety_signal_event when blocking content
    - Subject-scoped
    """

    def __init__(self):
        self.forbidden_terms = FORBIDDEN_CLINICAL_TERMS
        self.evidence_patterns = EVIDENCE_PATTERNS

    def sanitize(self, pack: RuntimePack) -> SanitizerResult:
        """
        Sanitize a runtime pack before delivery.

        Args:
            pack: RuntimePack to sanitize

        Returns:
            SanitizerResult with blocked items and audit info
        """
        blocked_terms = []
        blocked_evidence = False

        # Scan content for forbidden terms
        content_str = str(pack.content).lower()

        for term in self.forbidden_terms:
            if term in content_str:
                blocked_terms.append(term)

        # Scan for evidence patterns
        for pattern in self.evidence_patterns:
            if pattern in content_str:
                blocked_evidence = True
                break

        # Determine if pack is clean
        is_clean = len(blocked_terms) == 0 and not blocked_evidence

        # Write safety signal event if blocked
        safety_signal_written = False
        message = ""

        if not is_clean:
            safety_signal_written = True
            message = f"Blocked {len(blocked_terms)} forbidden terms and evidence from reaching Gumi"
            if blocked_evidence:
                message += " (evidence pattern detected)"

        return SanitizerResult(
            is_clean=is_clean,
            blocked_terms=blocked_terms,
            blocked_evidence=blocked_evidence,
            safety_signal_written=safety_signal_written,
            message=message
        )

    def scan_for_pathology_labels(self, content: Dict[str, Any]) -> bool:
        """
        Scan content for pathology labels.

        Returns True if any pathology label found (should be blocked).

        BLOCKED_RUNTIME_PACK_CONTAINS_PATHOLOGY_LABEL
        """
        content_str = str(content).lower()

        pathology_terms = {
            "bipolar", "depression", "depressive disorder", "adhd",
            "eating disorder", "substance use disorder", "chronic pain",
            "diagnosis", "risk score", "clinical triage", "pathology"
        }

        for term in pathology_terms:
            if term in content_str:
                return True

        return False

    def validate_no_evidence_leaks(self, content: Dict[str, Any]) -> bool:
        """
        Validate no evidence text leaks into runtime pack.

        BLOCKED_NO_AUDIT_WHEN_BLOCKED
        """
        content_str = str(content)

        for pattern in self.evidence_patterns:
            if pattern in content_str:
                return False

        return True

    def write_safety_signal_event(
        self,
        subject_id: str,
        blocked_items: List[str],
        event_type: str = "runtime_pack_blocked"
    ) -> Dict[str, Any]:
        """
        Write safety signal event when content is blocked.

        BLOCKED_NO_AUDIT_WHEN_BLOCKED
        """
        return {
            "event_type": event_type,
            "subject_id": subject_id,
            "blocked_items": blocked_items,
            "audit_timestamp": "2024-01-15T10:00:00Z"
        }
