"""Continuity to PromptContextPack adapter.

This adapter converts Shared Continuity (PR01/PR06) markers into
PromptContextPack continuity items. It is the ONLY path by which
continuity markers are admitted into injected runtime context.

Key guarantees:
- Only recall-eligible markers are admitted
- TTL, recall limits, pause, and burden are respected
- Clinical terms are never injected
- Subject scope is enforced
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from relic.shared_continuity.service import get_continuity_service, FORBIDDEN_CLINICAL_TERMS
from relic.gumi_continuity.admission import get_admission_policy, ContinuityAdmissionPolicy

try:
    import structlog
    logger = structlog.get_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)


@dataclass
class ContinuityContextItem:
    """A continuity item ready for PromptContextPack injection.
    
    This represents a recall-eligible marker that passes admission checks.
    """
    marker_id: str
    subject_id: str
    gumi_instance_id: str
    hermes_profile_id: str
    subject_words: list[str]
    source_type: str
    created_at: str
    recall_count: int = 0
    max_recall_count: int = 3
    expires_at: Optional[str] = None
    final_subject_words: Optional[list[str]] = None
    clinical_interpretation_allowed: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ContinuityAdmissionResult:
    """Result of continuity context adaptation.
    
    Contains all admitted continuity items and blocked markers.
    """
    admitted: list[ContinuityContextItem] = field(default_factory=list)
    blocked: list[str] = field(default_factory=list)  # blocked marker_ids
    blocked_reasons: dict[str, list[str]] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class ContinuityContextPackAdapter:
    """Adapter converting Shared Continuity markers to PromptContextPack format.
    
    This adapter is the ONLY path for continuity markers to enter
    runtime context. It enforces:
    - TTL: Only non-expired markers admitted
    - Recall limits: Only markers under max_recall_count admitted
    - Pause: Only non-paused scopes admitted
    - Burden: Limits number of markers in context
    - Clinical safety: No forbidden clinical terms
    """

    def __init__(
        self,
        admission_policy: Optional[ContinuityAdmissionPolicy] = None,
    ):
        self._admission_policy = admission_policy or get_admission_policy()

    def adapt(
        self,
        subject_id: str,
        gumi_instance_id: str,
        hermes_profile_id: str,
        limit: int = 10,
    ) -> ContinuityAdmissionResult:
        """Adapt continuity markers for a subject into context pack format.
        
        Args:
            subject_id: Subject identifier
            gumi_instance_id: Gumi instance identifier
            hermes_profile_id: Hermes profile identifier
            limit: Maximum number of markers to admit
            
        Returns:
            ContinuityAdmissionResult with admitted items and blocked markers
        """
        service = get_continuity_service()

        # Get recent markers from service (already filtered by subject scope)
        markers = service.recent_markers(
            subject_id=subject_id,
            gumi_instance_id=gumi_instance_id,
            hermes_profile_id=hermes_profile_id,
            limit=limit * 2,  # Get more to account for admission filtering
        )

        # Apply admission policy
        decisions = self._admission_policy.evaluate_markers(markers)

        admitted_items: list[ContinuityContextItem] = []
        blocked_marker_ids: list[str] = []
        blocked_reasons: dict[str, list[str]] = {}

        for i, decision in enumerate(decisions):
            marker = markers[i]

            if decision.admitted:
                # Check clinical terms
                marker_str = str(marker).lower()
                clinical_hits = [t for t in FORBIDDEN_CLINICAL_TERMS if t in marker_str]
                if clinical_hits:
                    blocked_marker_ids.append(decision.marker_id)
                    blocked_reasons.setdefault("clinical", []).append(decision.marker_id)
                    continue

                # Create continuity item
                item = ContinuityContextItem(
                    marker_id=marker.get("marker_id", ""),
                    subject_id=marker.get("subject_id", ""),
                    gumi_instance_id=marker.get("gumi_instance_id", ""),
                    hermes_profile_id=marker.get("hermes_profile_id", ""),
                    subject_words=marker.get("subject_words", []),
                    source_type=marker.get("source_type", ""),
                    created_at=marker.get("created_at", ""),
                    recall_count=marker.get("recall_count", 0),
                    max_recall_count=marker.get("max_recall_count", 3),
                    expires_at=marker.get("expires_at"),
                    final_subject_words=marker.get("final_subject_words"),
                    clinical_interpretation_allowed=marker.get("clinical_interpretation_allowed", False),
                    metadata={
                        "status": marker.get("status"),
                        "gumi_recall_allowed": marker.get("gumi_recall_allowed", True),
                    },
                )
                admitted_items.append(item)
            else:
                blocked_marker_ids.append(decision.marker_id)
                if decision.blocked_by:
                    blocked_reasons.setdefault(decision.blocked_by, []).append(decision.marker_id)

        return ContinuityAdmissionResult(
            admitted=admitted_items,
            blocked=blocked_marker_ids,
            blocked_reasons=blocked_reasons,
            metadata={
                "subject_id": subject_id,
                "gumi_instance_id": gumi_instance_id,
                "hermes_profile_id": hermes_profile_id,
                "total_markers": len(markers),
                "admitted_count": len(admitted_items),
                "blocked_count": len(blocked_marker_ids),
            },
        )

    def adapt_to_dict(
        self,
        subject_id: str,
        gumi_instance_id: str,
        hermes_profile_id: str,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Adapt continuity markers and return as dict for serialization.
        
        Args:
            subject_id: Subject identifier
            gumi_instance_id: Gumi instance identifier
            hermes_profile_id: Hermes profile identifier
            limit: Maximum number of markers to admit
            
        Returns:
            Dict representation suitable for PromptContextPack
        """
        result = self.adapt(subject_id, gumi_instance_id, hermes_profile_id, limit)

        return {
            "continuity_items": [
                {
                    "marker_id": item.marker_id,
                    "subject_id": item.subject_id,
                    "subject_words": item.subject_words,
                    "final_subject_words": item.final_subject_words,
                    "source_type": item.source_type,
                    "created_at": item.created_at,
                    "recall_count": item.recall_count,
                    "max_recall_count": item.max_recall_count,
                    "expires_at": item.expires_at,
                    "clinical_interpretation_allowed": item.clinical_interpretation_allowed,
                    "metadata": item.metadata,
                }
                for item in result.admitted
            ],
            "blocked_markers": result.blocked,
            "blocked_reasons": result.blocked_reasons,
            "metadata": result.metadata,
        }


# Global adapter instance
_adapter: Optional[ContinuityContextPackAdapter] = None


def get_continuity_context_pack_adapter() -> ContinuityContextPackAdapter:
    """Get the global continuity context pack adapter instance."""
    global _adapter
    if _adapter is None:
        _adapter = ContinuityContextPackAdapter()
    return _adapter
