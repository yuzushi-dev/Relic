"""
Safety Signal Extractor.

Maps event streams to allowed signal families only, producing no diagnosis labels.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any


class SignalFamily(Enum):
    """Allowed signal families - no diagnosis labels."""
    DEPENDENCY_ESCALATION = "dependency_escalation"
    EXCLUSIVE_ATTACHMENT_LANGUAGE = "exclusive_attachment_language"
    ROMANTIC_BOUNDARY_PRESSURE = "romantic_boundary_pressure"
    GUMI_OVERREACH = "gumi_overreach"
    PROACTIVE_BURDEN = "proactive_burden"
    DISTRESS_AFTER_NONRESPONSE = "distress_after_nonresponse"
    BACKEND_DISCLOSURE_PRESSURE = "backend_disclosure_pressure"
    USER_OPT_OUT_PRESSURE = "user_opt_out_pressure"
    CAREFUL_DISTANCING_NEEDED = "careful_distancing_needed"
    MEDICAL_ADVICE_REQUEST = "medical_advice_request"
    PSYCHOLOGICAL_ADVICE_REQUEST = "psychological_advice_request"
    CRISIS_LANGUAGE = "crisis_language"
    SELF_HARM_LANGUAGE = "self_harm_language"
    SENSITIVE_HEALTH_CONTEXT = "sensitive_health_context"
    SENSITIVE_MENTAL_HEALTH_CONTEXT = "sensitive_mental_health_context"
    SLEEP_ENERGY_CONTEXT = "sleep_energy_context"
    PAIN_FATIGUE_CONTEXT = "pain_fatigue_context"
    FOOD_BODY_CONTROL_CONTEXT = "food_body_control_context"
    SUBSTANCE_RELATED_CONTEXT = "substance_related_context"
    LEGAL_OR_FINANCIAL_HIGH_STAKES_REQUEST = "legal_or_financial_high_stakes_request"


class CrisisSignal(Enum):
    """Signals that bypass pattern matching."""
    CRISIS_LANGUAGE = "crisis_language"
    SELF_HARM_LANGUAGE = "self_harm_language"


# Confidence caps
SINGLE_EVENT_CAP = 0.30
TWO_EVENTS_CAP = 0.55
THREE_OR_MORE_CAP = 0.75
HUMAN_REVIEWED_CAP = 0.85
BASELINE_UNKNOWN_CAP = 0.35
MAXIMUM_CAP = 0.85

# Evidence requirements
MULTIPLE_EVENTS_REQUIRED = {"dependency_escalation", "exclusive_attachment_language",
                            "distress_after_nonresponse", "sleep_energy_context",
                            "pain_fatigue_context", "food_body_control_context"}

FORBIDDEN_LABELS = {
    "bipolar", "depression", "ADHD", "eating disorder",
    "substance use disorder", "chronic pain", "medical condition",
    "diagnosis", "risk score", "clinical triage", "therapy", "medical advice"
}


@dataclass
class SensitiveSignal:
    """A sensitive signal with subject scope."""
    subject_id: str
    gumi_instance_id: str
    hermes_profile_id: str
    signal_family: str
    evidence_refs: List[str]
    confidence: float
    subject_visible: bool = False
    gumi_visible_label: bool = False
    clinical_interpretation_allowed: bool = False
    baseline_comparison: Optional[Dict[str, float]] = None
    event_count: int = 1
    human_reviewed: bool = False
    status: str = "pending"


@dataclass
class ExtractedSignals:
    """Result of signal extraction."""
    signals: List[SensitiveSignal]
    crisis_bypassed: bool = False
    crisis_signal_type: Optional[str] = None


class SafetySignalExtractor:
    """
    Extracts sensitive signals from event streams.

    Only produces allowed signal families. No diagnosis labels.
    Crisis signals bypass processing entirely.
    """

    def __init__(self):
        self.allowed_families = {f.value for f in SignalFamily}
        self.crisis_signals = {f.value for f in CrisisSignal}

    def extract(
        self,
        subject_id: str,
        gumi_instance_id: str,
        hermes_profile_id: str,
        events: List[Dict[str, Any]],
        baseline_confidence: Optional[float] = None
    ) -> ExtractedSignals:
        """
        Extract sensitive signals from event batch.

        Args:
            subject_id: Subject identifier
            gumi_instance_id: Gumi instance identifier
            hermes_profile_id: Hermes profile identifier
            events: List of events to process
            baseline_confidence: Optional baseline for comparison

        Returns:
            ExtractedSignals containing signals and crisis bypass info
        """
        # Check for crisis signals first (bypass)
        for event in events:
            event_text = event.get("text", "").lower()
            for crisis in self.crisis_signals:
                if self._matches_crisis(event_text, crisis):
                    return ExtractedSignals(
                        signals=[],
                        crisis_bypassed=True,
                        crisis_signal_type=crisis
                    )

        # Process non-crisis events
        signals = []
        event_signals: Dict[str, List[str]] = {}

        for event in events:
            event_text = event.get("text", "")
            signal_family = self._classify_event(event_text)
            if not signal_family:
                continue
            # Defense in depth: must be an allowed family AND must not match the
            # diagnosis denylist (guards against future _classify_event bugs).
            if signal_family not in self.allowed_families:
                continue
            if signal_family in self.forbidden_labels:
                continue
            if signal_family not in event_signals:
                event_signals[signal_family] = []
            event_signals[signal_family].append(event.get("event_id", "unknown"))

        # Build signals with confidence caps
        for family, refs in event_signals.items():
            event_count = len(refs)
            confidence = self._calculate_confidence(event_count, baseline_confidence)

            signal = SensitiveSignal(
                subject_id=subject_id,
                gumi_instance_id=gumi_instance_id,
                hermes_profile_id=hermes_profile_id,
                signal_family=family,
                evidence_refs=refs,
                confidence=confidence,
                event_count=event_count,
                baseline_comparison=self._build_baseline_comparison(
                    baseline_confidence, confidence
                ) if baseline_confidence else None
            )
            signals.append(signal)

        return ExtractedSignals(signals=signals)

    def _matches_crisis(self, text: str, crisis_type: str) -> bool:
        """Check if text matches crisis signal."""
        if crisis_type == "crisis_language":
            crisis_keywords = ["suicide", "kill myself", "end it all", "self harm"]
            return any(kw in text for kw in crisis_keywords)
        elif crisis_type == "self_harm_language":
            harm_keywords = ["hurt myself", "cut myself", "harm myself"]
            return any(kw in text for kw in harm_keywords)
        return False

    def _classify_event(self, text: str) -> Optional[str]:
        """
        Classify event text into signal family.

        Returns allowed family or None. Never returns diagnosis labels.
        """
        text_lower = text.lower()

        # Map text patterns to allowed families
        patterns = {
            "dependency_escalation": ["relying on you more", "cant cope without", "need you all the time"],
            "exclusive_attachment_language": ["dont leave me", "youre the only one", "cant live without you"],
            "romantic_boundary_pressure": ["love me more", "choose me over", "if you loved me"],
            "gumi_overreach": ["you should know", "i want full access", "show me everything"],
            "proactive_burden": ["i burden everyone", "i am too much", "drag everyone down"],
            "distress_after_nonresponse": ["why wont you respond", "you ignore me", "left me hanging"],
            "careful_distancing_needed": ["give me space", "need distance", "too close"],
            "medical_advice_request": ["should i see a doctor", "is this normal", "medical question"],
            "psychological_advice_request": ["how do i cope", "what should i do", "help me understand"],
            "sleep_energy_context": ["cant sleep", "exhausted", "so tired", "no energy"],
            "pain_fatigue_context": ["in pain", "chronic pain", "exhausted", "fatigue"],
            "food_body_control_context": ["cant stop eating", "food control", "body image"],
            "substance_related_context": ["drink to cope", "need a drink", "substance"],
            "legal_or_financial_high_stakes_request": ["sue me", "legal advice", "financial trouble"],
        }

        for family, keywords in patterns.items():
            if any(kw in text_lower for kw in keywords):
                return family

        return None

    def _calculate_confidence(
        self,
        event_count: int,
        baseline_confidence: Optional[float] = None
    ) -> float:
        """Calculate confidence capped by event count rules."""
        if baseline_confidence is not None:
            # Use baseline unknown cap
            return min(baseline_confidence, BASELINE_UNKNOWN_CAP)

        if event_count == 1:
            return SINGLE_EVENT_CAP
        elif event_count == 2:
            return TWO_EVENTS_CAP
        else:
            return THREE_OR_MORE_CAP

    def _build_baseline_comparison(
        self,
        baseline: float,
        current: float
    ) -> Dict[str, float]:
        """Build baseline comparison data."""
        return {
            "baseline_confidence": baseline,
            "current_confidence": current,
            "delta": current - baseline
        }

    @property
    def forbidden_labels(self) -> set:
        """Return forbidden labels set."""
        return FORBIDDEN_LABELS
