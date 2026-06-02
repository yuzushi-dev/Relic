"""
PR33E, Hermes Plugin Tools for Shared Continuity Memory

Tools that call the Relic continuity service (not direct DB access).
Tools return no clinical terms to Gumi.
Tools require subject_id, gumi_instance_id, hermes_profile_id.
Tools validate subject confirmation before write operations.
Tools scope results to subject.
"""

from typing import Dict, Any, Optional, List

from relic.shared_continuity.service import (
    get_continuity_service,
    FORBIDDEN_CLINICAL_TERMS,
)

# From .schemas and .tools
from .schemas import TOOL_SCHEMAS
from .tools import HANDLERS
from .hooks import pre_llm_call, post_llm_call, transform_llm_output


class SharedContinuityTools:
    """Hermes plugin tools for Shared Continuity Memory."""

    def __init__(self):
        self._service = get_continuity_service()

    def _validate_subject_scope_write(
        self,
        subject_id: str,
        gumi_instance_id: Optional[str] = None,
        hermes_profile_id: Optional[str] = None,
    ) -> None:
        """Validate that all subject scope fields are present for write operations."""
        if not subject_id:
            raise ValueError("BLOCKED_MARKER_WITHOUT_SUBJECT_SCOPE: subject_id required")
        if not gumi_instance_id:
            raise ValueError("BLOCKED_MARKER_WITHOUT_SUBJECT_SCOPE: gumi_instance_id required")
        if not hermes_profile_id:
            raise ValueError("BLOCKED_MARKER_WITHOUT_SUBJECT_SCOPE: hermes_profile_id required")

    def _validate_subject_scope_read(
        self,
        subject_id: str,
    ) -> None:
        """Validate that subject_id is present for read operations."""
        if not subject_id:
            raise ValueError("BLOCKED_MARKER_WITHOUT_SUBJECT_SCOPE: subject_id required")

    def _check_no_clinical_terms(self, data: Any) -> None:
        """Check that data contains no forbidden clinical terms."""
        data_str = str(data).lower()
        for term in FORBIDDEN_CLINICAL_TERMS:
            if term in data_str:
                raise ValueError(f"BLOCKED_CLINICAL_LABEL_IN_RUNTIME: {term} found in output")

    def tool_remember_marker(
        self,
        subject_id: str,
        gumi_instance_id: str,
        hermes_profile_id: str,
        subject_words: List[str],
        source_type: str = "user_confirmed",
        max_recall_count: int = 3,
        ttl_seconds: int = 604800,
        subject_confirmation: bool = True,
    ) -> Dict[str, Any]:
        """Remember a continuity marker. Requires subject confirmation before storing."""
        self._validate_subject_scope_write(subject_id, gumi_instance_id, hermes_profile_id)
        result = self._service.remember(
            subject_id=subject_id,
            gumi_instance_id=gumi_instance_id,
            hermes_profile_id=hermes_profile_id,
            subject_words=subject_words,
            source_type=source_type,
            max_recall_count=max_recall_count,
            ttl_seconds=ttl_seconds,
            subject_confirmation=subject_confirmation,
        )
        self._check_no_clinical_terms(result)
        return result

    def tool_correct_marker(
        self,
        subject_id: str,
        gumi_instance_id: str,
        hermes_profile_id: str,
        marker_id: str,
        subject_words: List[str],
        created_by: str = "subject",
    ) -> Dict[str, Any]:
        """Correct a marker. Marks old marker retired and stores correction as authoritative."""
        self._validate_subject_scope_write(subject_id, gumi_instance_id, hermes_profile_id)
        result = self._service.correct(
            marker_id=marker_id,
            subject_id=subject_id,
            gumi_instance_id=gumi_instance_id,
            hermes_profile_id=hermes_profile_id,
            subject_words=subject_words,
            created_by=created_by,
        )
        self._check_no_clinical_terms(result)
        return result

    def tool_get_due_followups(
        self,
        subject_id: str,
        gumi_instance_id: Optional[str] = None,
        hermes_profile_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get markers where followup is due and not exhausted. Respects pause state."""
        self._validate_subject_scope_read(subject_id)
        results = self._service.due_followups(
            subject_id=subject_id,
            gumi_instance_id=gumi_instance_id,
            hermes_profile_id=hermes_profile_id,
        )
        for result in results:
            self._check_no_clinical_terms(result)
        return results

    def tool_get_recent_markers(
        self,
        subject_id: str,
        gumi_instance_id: Optional[str] = None,
        hermes_profile_id: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get recent subject-confirmed markers."""
        self._validate_subject_scope_read(subject_id)
        results = self._service.recent_markers(
            subject_id=subject_id,
            gumi_instance_id=gumi_instance_id,
            hermes_profile_id=hermes_profile_id,
            limit=limit,
        )
        for result in results:
            self._check_no_clinical_terms(result)
        return results

    def tool_forget_marker(
        self,
        subject_id: str,
        marker_id: str,
    ) -> Dict[str, Any]:
        """Remove marker from Gumi recall without deleting from storage."""
        if not subject_id:
            raise ValueError("BLOCKED_MARKER_WITHOUT_SUBJECT_SCOPE: subject_id required")
        result = self._service.forget(marker_id=marker_id, subject_id=subject_id)
        self._check_no_clinical_terms(result)
        return result

    def tool_pause_scope(
        self,
        subject_id: str,
        scope_name: str = "global",
        gumi_instance_id: Optional[str] = None,
        hermes_profile_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Block follow-ups from paused scope."""
        self._validate_subject_scope_read(subject_id)
        result = self._service.pause(
            subject_id=subject_id,
            scope_name=scope_name,
            gumi_instance_id=gumi_instance_id,
            hermes_profile_id=hermes_profile_id,
        )
        self._check_no_clinical_terms(result)
        return result

    def tool_resume_scope(
        self,
        subject_id: str,
        scope_name: str = "global",
        gumi_instance_id: Optional[str] = None,
        hermes_profile_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Restore follow-ups."""
        self._validate_subject_scope_read(subject_id)
        result = self._service.resume(
            subject_id=subject_id,
            scope_name=scope_name,
            gumi_instance_id=gumi_instance_id,
            hermes_profile_id=hermes_profile_id,
        )
        self._check_no_clinical_terms(result)
        return result


# Global tools instance
_tools = SharedContinuityTools()


def get_shared_continuity_tools() -> SharedContinuityTools:
    """Get the global tools instance."""
    return _tools


def register(ctx):
    """Register tools and hooks with Hermes context."""
    for name, schema in TOOL_SCHEMAS.items():
        ctx.register_tool(name, schema, HANDLERS[name])
    ctx.register_hook("pre_llm_call", pre_llm_call)
    ctx.register_hook("post_llm_call", post_llm_call)
    ctx.register_hook("transform_llm_output", transform_llm_output)
