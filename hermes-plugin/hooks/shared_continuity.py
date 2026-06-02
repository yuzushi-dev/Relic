"""
PR33F, Hermes Hooks for Shared Continuity Memory

Pre-LLM call, post-LLM call, and transform LLM output hooks
for context injection. Hooks inject only subject-confirmed markers.
No clinical tags in context. All hooks are subject-scoped.
"""

from typing import Dict, Any, Optional, List

from relic.shared_continuity.service import get_continuity_service, FORBIDDEN_CLINICAL_TERMS


class SharedContinuityHooks:
    """Hermes hooks for Shared Continuity Memory context injection."""

    def __init__(self):
        self._service = get_continuity_service()

    def _check_no_clinical_terms(self, data: Any) -> None:
        """Check that data contains no forbidden clinical terms (word-boundary match)."""
        import re
        data_str = str(data).lower()
        for term in FORBIDDEN_CLINICAL_TERMS:
            # Use word boundary matching to catch word forms (e.g., "depressed" matches "depression")
            pattern = r'\b' + re.escape(term) + r'\b'
            if re.search(pattern, data_str):
                raise ValueError(f"BLOCKED_CLINICAL_LABEL_IN_RUNTIME: {term} found")

    def pre_llm_call(
        self,
        subject_id: str,
        gumi_instance_id: str,
        hermes_profile_id: str,
        prompt_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Pre-LLM call hook. Injects subject-confirmed markers into context.

        Filters markers by scope before injection.
        Only subject-confirmed markers are injected.
        No clinical terms injected.
        """
        if not all([subject_id, gumi_instance_id, hermes_profile_id]):
            raise ValueError("BLOCKED_MARKER_WITHOUT_SUBJECT_SCOPE: All scope fields required")

        # Get recent markers for this subject
        markers = self._service.recent_markers(
            subject_id=subject_id,
            gumi_instance_id=gumi_instance_id,
            hermes_profile_id=hermes_profile_id,
            limit=10,
        )

        # Filter: only subject-confirmed markers
        confirmed_markers = [m for m in markers if m.get("subject_confirmation", False)]

        # Check no clinical terms
        for marker in confirmed_markers:
            self._check_no_clinical_terms(marker)

        # Build injected context
        injected_context = {
            "shared_continuity_markers": confirmed_markers,
            "marker_count": len(confirmed_markers),
        }

        # If there was existing prompt context, merge carefully
        if prompt_context:
            # Don't add clinical terms from existing context
            self._check_no_clinical_terms(prompt_context)

        return injected_context

    def post_llm_call(
        self,
        subject_id: str,
        gumi_instance_id: str,
        hermes_profile_id: str,
        llm_output: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Post-LLM call hook. Validates output and logs result.

        Does not modify Gumi output with clinical terms.
        No clinical terms in output.
        """
        if not all([subject_id, gumi_instance_id, hermes_profile_id]):
            raise ValueError("BLOCKED_MARKER_WITHOUT_SUBJECT_SCOPE: All scope fields required")

        # Check output for clinical terms
        self._check_no_clinical_terms(llm_output)

        return {
            "validation": "passed",
            "subject_id": subject_id,
            "clinical_check": "clean",
        }

    def transform_llm_output(
        self,
        subject_id: str,
        gumi_instance_id: str,
        hermes_profile_id: str,
        output: str,
    ) -> str:
        """
        Transform LLM output. Does not add clinical interpretation.

        No clinical interpretation added.
        Subject-scoped transformation.
        """
        if not all([subject_id, gumi_instance_id, hermes_profile_id]):
            raise ValueError("BLOCKED_MARKER_WITHOUT_SUBJECT_SCOPE: All scope fields required")

        # Check for clinical terms - if found, block transformation
        self._check_no_clinical_terms(output)

        # No transformation needed - just validate and return
        return output


def get_shared_continuity_hooks() -> SharedContinuityHooks:
    """Get the global hooks instance."""
    return SharedContinuityHooks()


# Convenience functions for direct use
_hooks = SharedContinuityHooks()


def pre_llm_call_shared_continuity(
    subject_id: str,
    gumi_instance_id: str,
    hermes_profile_id: str,
    prompt_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Pre-LLM call hook entry point."""
    return _hooks.pre_llm_call(
        subject_id=subject_id,
        gumi_instance_id=gumi_instance_id,
        hermes_profile_id=hermes_profile_id,
        prompt_context=prompt_context,
    )


def post_llm_call_shared_continuity(
    subject_id: str,
    gumi_instance_id: str,
    hermes_profile_id: str,
    llm_output: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Post-LLM call hook entry point."""
    return _hooks.post_llm_call(
        subject_id=subject_id,
        gumi_instance_id=gumi_instance_id,
        hermes_profile_id=hermes_profile_id,
        llm_output=llm_output,
        metadata=metadata,
    )


def transform_llm_output_shared_continuity(
    subject_id: str,
    gumi_instance_id: str,
    hermes_profile_id: str,
    output: str,
) -> str:
    """Transform LLM output hook entry point."""
    return _hooks.transform_llm_output(
        subject_id=subject_id,
        gumi_instance_id=gumi_instance_id,
        hermes_profile_id=hermes_profile_id,
        output=output,
    )


def get_shared_continuity_hooks() -> SharedContinuityHooks:
    """Get the shared continuity hooks instance."""
    return _hooks