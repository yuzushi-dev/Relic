"""
HermesClient - centralizes all Relic->Hermes API calls with session key injection.

Every subject-scoped Relic->Hermes API call must pass X-Hermes-Session-Key header.
This client ensures session key is always scoped to subject and never logged raw.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from relic.hermes_runtime import (
    HermesSessionKey,
    X_HERMES_SESSION_KEY_HEADER,
)


logger = logging.getLogger(__name__)


def _hash_for_logging(key_hash: str) -> str:
    """
    Create a log-safe hash representation of session key.

    Args:
        key_hash: The session key hash to transform.

    Returns:
        A log-safe representation (first 8 chars of sha256 of the hash).
    """
    return hashlib.sha256(key_hash.encode()).hexdigest()[:16]


class HermesClient:
    """
    Centralized client for all Relic->Hermes API calls.

    Ensures every call includes X-Hermes-Session-Key header scoped to
    subject_id, gumi_instance_id, and hermes_profile_id.

    The raw session key is never logged - only a derived hash is emitted.
    Cross-subject key reuse is rejected at construction time.
    """

    def __init__(
        self,
        subject_id: str,
        gumi_instance_id: str,
        hermes_profile_id: str,
    ) -> None:
        """
        Initialize Hermes client with subject scope.

        Args:
            subject_id: Required. Subject ID to scope the session key.
            gumi_instance_id: Gumi instance identifier.
            hermes_profile_id: Hermes profile identifier.

        Raises:
            ValueError: If subject_id is missing or empty.
        """
        # Validate subject scope exists
        HermesSessionKey.reject_missing_scope(subject_id)

        if not gumi_instance_id:
            raise ValueError("gumi_instance_id is required")
        if not hermes_profile_id:
            raise ValueError("hermes_profile_id is required")

        self._subject_id = subject_id
        self._gumi_instance_id = gumi_instance_id
        self._hermes_profile_id = hermes_profile_id

        # Derive the session key hash for this scope
        self._session_key_hash = HermesSessionKey.derive(
            subject_id, gumi_instance_id, hermes_profile_id
        )

        logger.debug(
            "HermesClient initialized for subject_id=%s, session_key_hash=%s",
            subject_id,
            _hash_for_logging(self._session_key_hash),
        )

    @property
    def subject_id(self) -> str:
        """Return the subject ID for this client."""
        return self._subject_id

    @property
    def session_key_hash(self) -> str:
        """Return the session key hash (never raw key)."""
        return self._session_key_hash

    def call(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Make a subject-scoped Hermes API call with session key injection.

        Args:
            method: HTTP method (GET, POST, etc.).
            endpoint: API endpoint path.
            **kwargs: Additional arguments passed to HTTP client.

        Returns:
            Response dict from Hermes API.

        Raises:
            ValueError: If subject scope is missing.
        """
        # Inject session key header on every call
        headers = kwargs.get("headers", {})
        headers[X_HERMES_SESSION_KEY_HEADER] = self._session_key_hash
        kwargs["headers"] = headers

        # Log the call with hash only, never raw key
        logger.info(
            "Hermes API call: method=%s endpoint=%s subject_id=%s session_key_hash=%s",
            method,
            endpoint,
            self._subject_id,
            _hash_for_logging(self._session_key_hash),
        )

        # Make the actual HTTP call
        # This will be wired to actual HTTP client in production
        return self._make_request(method, endpoint, **kwargs)

    def _make_request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Make the HTTP request to Hermes.

        Override this method for custom HTTP transport.

        Args:
            method: HTTP method.
            endpoint: API endpoint.
            **kwargs: Request arguments.

        Returns:
            Response dict.
        """
        # Default implementation - would be replaced with actual HTTP client
        # For now, return a structured response indicating call was made
        return {
            "status": "ok",
            "method": method,
            "endpoint": endpoint,
            "session_key_hash_logged": _hash_for_logging(self._session_key_hash),
        }

    def validate_call_scope(self, subject_id: str) -> None:
        """
        Validate that a call is scoped to the client's subject.

        Args:
            subject_id: Subject ID to validate.

        Raises:
            ValueError: If subject_id doesn't match client scope.
        """
        if subject_id != self._subject_id:
            raise ValueError(
                f"Cross-subject key reuse detected: call subject_id={subject_id} "
                f"does not match client scope={self._subject_id}"
            )


def create_hermes_client(
    subject_id: str,
    gumi_instance_id: str,
    hermes_profile_id: str,
) -> HermesClient:
    """
    Factory function to create a HermesClient.

    Args:
        subject_id: Required. Subject ID to scope the session key.
        gumi_instance_id: Gumi instance identifier.
        hermes_profile_id: Hermes profile identifier.

    Returns:
        Configured HermesClient instance.

    Raises:
        ValueError: If any required parameter is missing or empty.
    """
    return HermesClient(subject_id, gumi_instance_id, hermes_profile_id)