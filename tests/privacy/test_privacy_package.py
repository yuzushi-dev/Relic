"""PR04, assert the modular privacy package surface and fail-closed defaults."""
from __future__ import annotations

import pytest

from relic.privacy import (
    PrivacyDecision,
    PrivacyGateway,
    PrivacyPolicy,
    classify_inference,
    detect_pii,
    load_policy,
    redact_pii,
)


def test_default_policy_blocks_logging() -> None:
    p = PrivacyPolicy.default()
    assert p.raw_prompt_logging is False
    assert p.rehydration_allowed is False
    assert p.final_output_gate_enabled is True


def test_loaded_policy_matches_yaml() -> None:
    pol = load_policy()
    assert "credentials" in pol.sensitive_categories


def test_pii_detector_finds_email_and_phone() -> None:
    hits = detect_pii("contact me at jane@example.com or +1 555 123 4567")
    cats = {h.category for h in hits}
    assert "email" in cats and "phone" in cats


def test_pii_redaction_removes_sensitive() -> None:
    redacted = redact_pii("send to admin@example.com")
    assert "admin@example.com" not in redacted


def test_inference_classifier_flags_credentials() -> None:
    v = classify_inference("paste your API key here")
    assert v.category == "credentials"


def test_gateway_blocks_credentials() -> None:
    gw = PrivacyGateway()
    decision: PrivacyDecision = gw.decide("share my password 12345", stage="output")
    assert decision.decision in {"BLOCK", "REDACT"}


def test_gateway_blocks_rehydration_attempt() -> None:
    gw = PrivacyGateway()
    decision = gw.decide("hello", rehydration_attempt=True)
    assert decision.rehydration_blocked is True
    assert decision.decision == "BLOCK"
