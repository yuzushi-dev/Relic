"""
Behavior Policy Compiler.

Converts sensitive signals to label-stripped gumi_behavior_policy_patch
containing only constraint vocabulary.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


# Constraint vocabulary - no family names allowed
CONSTRAINT_VOCABULARY = [
    "allow",
    "deny",
    "limit",
    "monitor",
    "escalate",
    "redirect",
    "block",
    "require_review",
    "careful_delivery",
    "maintain_boundaries",
    "respect_opt_out",
    "non_delivery"
]

# Family name to constraints mapping
FAMILY_CONSTRAINTS = {
    "dependency_escalation": ["monitor", "maintain_boundaries", "careful_delivery"],
    "exclusive_attachment_language": ["maintain_boundaries", "monitor", "careful_delivery"],
    "romantic_boundary_pressure": ["maintain_boundaries", "careful_delivery"],
    "gumi_overreach": ["deny", "block", "require_review"],
    "proactive_burden": ["monitor", "careful_delivery", "allow"],
    "distress_after_nonresponse": ["careful_delivery", "monitor"],
    "backend_disclosure_pressure": ["deny", "block", "require_review"],
    "user_opt_out_pressure": ["allow", "respect_opt_out", "deny"],
    "careful_distancing_needed": ["maintain_boundaries", "careful_delivery"],
    "medical_advice_request": ["escalate", "require_review"],
    "psychological_advice_request": ["escalate", "require_review"],
    "sensitive_health_context": ["monitor", "escalate"],
    "sensitive_mental_health_context": ["monitor", "escalate"],
    "sleep_energy_context": ["monitor"],
    "pain_fatigue_context": ["monitor", "escalate"],
    "food_body_control_context": ["monitor", "escalate"],
    "substance_related_context": ["escalate", "require_review"],
    "legal_or_financial_high_stakes_request": ["require_review", "escalate"]
}

# Crisis signals produce specific constraints
CRISIS_CONSTRAINTS = ["escalate", "require_review", "non_delivery"]


@dataclass
class BehaviorPolicyPatch:
    """
    Label-stripped behavior policy patch for Gumi.

    Contains only constraint vocabulary. No family names, no evidence text.
    Subject-scoped only.
    """
    subject_id: str
    gumi_instance_id: str
    constraints: List[str]
    policy_version: str = "1.0.0"
    rationale: Optional[str] = None
    signal_refs: List[str] = field(default_factory=list)


class BehaviorPolicyCompiler:
    """
    Compiles sensitive signals into behavior policy patches.

    Key rules:
    - Output contains ONLY constraint vocabulary
    - No family names in patch
    - No evidence text in patch
    - No clinical terms in patch
    - Patch is subject-scoped
    """

    def __init__(self):
        self.constraint_vocabulary = set(CONSTRAINT_VOCABULARY)
        self.family_constraints = FAMILY_CONSTRAINTS

    def compile(
        self,
        subject_id: str,
        gumi_instance_id: str,
        signal_refs: List[str],
        signal_families: List[str],
        crisis_signals: Optional[List[str]] = None
    ) -> BehaviorPolicyPatch:
        """
        Compile signals into a behavior policy patch.

        Args:
            subject_id: Subject identifier (required for scope)
            gumi_instance_id: Gumi instance identifier
            signal_refs: Internal signal references
            signal_families: List of signal families detected
            crisis_signals: Optional crisis signals (bypass type)

        Returns:
            BehaviorPolicyPatch with only constraint vocabulary
        """
        constraints = set()

        # Crisis signals get special constraints
        if crisis_signals:
            for crisis in crisis_signals:
                constraints.update(CRISIS_CONSTRAINTS)
        else:
            # Map families to constraints
            for family in signal_families:
                if family in self.family_constraints:
                    constraints.update(self.family_constraints[family])

        # Validate all constraints are in vocabulary
        self._validate_constraints(constraints)

        return BehaviorPolicyPatch(
            subject_id=subject_id,
            gumi_instance_id=gumi_instance_id,
            constraints=sorted(list(constraints)),
            policy_version="1.0.0",
            rationale="Sensitive context detected - apply constraints",
            signal_refs=signal_refs
        )

    def _validate_constraints(self, constraints: set) -> None:
        """
        Validate constraints contain only vocabulary.

        BLOCKED_PATCH_CONTAINS_FAMILY_NAME
        BLOCKED_PATCH_CONTAINS_CLINICAL_TERM
        """
        # All constraints must be in vocabulary
        for constraint in constraints:
            if constraint not in self.constraint_vocabulary:
                raise ValueError(
                    f"Constraint '{constraint}' not in vocabulary. "
                    "Patch must only contain constraint vocabulary."
                )

    def get_allowed_constraints(self) -> List[str]:
        """Return list of allowed constraints."""
        return sorted(CONSTRAINT_VOCABULARY)

    def is_constraint_allowed(self, constraint: str) -> bool:
        """Check if constraint is in allowed vocabulary."""
        return constraint in self.constraint_vocabulary

    def patch_contains_only_constraints(self, patch: BehaviorPolicyPatch) -> bool:
        """
        Validate patch contains only constraints.

        BLOCKED_PATCH_CONTAINS_FAMILY_NAME
        BLOCKED_PATCH_CONTAINS_CLINICAL_TERM
        """
        for constraint in patch.constraints:
            if constraint not in self.constraint_vocabulary:
                return False
        return True
