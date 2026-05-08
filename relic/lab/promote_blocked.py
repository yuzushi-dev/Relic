"""Promote blocked module for adapter training labs.

This module defines the contract for adapter promotion commands,
ensuring promotion cannot change runtime state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PromoteCommandStatus(Enum):
    """Status of a promote command."""

    BLOCKED = "blocked"
    STUBBED = "stubbed"
    NOT_IMPLEMENTED = "not_implemented"


@dataclass
class PromoteResult:
    """Result of a promote operation.

    Attributes:
        status: Current status of the operation.
        can_promote: Whether promotion is allowed.
        message: Human-readable message.
        details: Additional details about the operation.
    """

    status: PromoteCommandStatus = PromoteCommandStatus.BLOCKED
    can_promote: bool = False
    message: str = "Promotion is blocked."
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for reporting."""
        return {
            "status": self.status.value,
            "can_promote": self.can_promote,
            "message": self.message,
            "details": self.details,
        }


@dataclass
class PromoteBlocked:
    """Contract for adapter promotion operations.

    This contract ensures:
    - Promotion is stubbed and blocked by default
    - Runtime state cannot be modified by promotion
    - No actual deployment occurs
    """

    is_promote_blocked: bool = True
    runtime_safe: bool = True

    def promote(
        self,
        adapter_id: str | None = None,
        target_env: str | None = None,
    ) -> PromoteResult:
        """Attempt to promote an adapter.

        This operation is always blocked to prevent runtime modifications.

        Args:
            adapter_id: ID of the adapter to promote (ignored).
            target_env: Target environment (ignored).

        Returns:
            PromoteResult indicating the operation is blocked.
        """
        return PromoteResult(
            status=PromoteCommandStatus.BLOCKED,
            can_promote=False,
            message=(
                "Adapter promotion is blocked for security reasons. "
                "Runtime state cannot be modified through promotion operations."
            ),
            details={
                "adapter_id": adapter_id,
                "target_env": target_env,
                "runtime_affected": False,
                "blocked_reason": "Promotion is not available in this environment.",
            },
        )

    def check_can_promote(self) -> tuple[bool, str]:
        """Check if promotion can proceed.

        Returns:
            Tuple of (can_promote, reason). Always returns (False, reason).
        """
        return (
            False,
            "Promotion is blocked. Adapters cannot be promoted to runtime environments."
        )

    def get_blocked_report(self) -> dict[str, Any]:
        """Get a report indicating promotion is blocked.

        Returns:
            Dictionary with blocked status and details.
        """
        return {
            "status": "blocked",
            "can_promote": False,
            "message": "Promotion is not available.",
            "runtime_affected": False,
            "reason": "Promote command is stubbed and blocked.",
            "details": {
                "security_policy": "Adapters cannot modify runtime state",
                "blocked_operations": ["promote", "deploy", "activate"],
            },
        }


def generate_blocked_report(
    adapter_id: str | None = None,
    target_env: str | None = None,
) -> PromoteResult:
    """Generate a blocked promotion report.

    Args:
        adapter_id: Optional adapter ID.
        target_env: Optional target environment.

    Returns:
        PromoteResult indicating the operation is blocked.
    """
    blocker = PromoteBlocked()
    return blocker.promote(adapter_id=adapter_id, target_env=target_env)
