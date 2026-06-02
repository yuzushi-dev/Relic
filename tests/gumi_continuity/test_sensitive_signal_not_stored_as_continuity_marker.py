"""PR06-T12, PR32 sensitive_signals must never enter continuity marker store."""
from __future__ import annotations

from relic.gumi_continuity.admission import ContinuityAdmissionPolicy
from relic.gumi_continuity.store import GumiContinuityStore


def _make_sensitive_signal_candidate() -> dict:
    """Fixture: a candidate whose origin is a PR32 sensitive_signal."""
    return {
        "marker_id": "sig-001",
        "subject_id": "subj-1",
        "gumi_instance_id": "gumi-1",
        "hermes_profile_id": "hermes-1",
        "status": "active",
        "gumi_recall_allowed": True,
        "recall_count": 0,
        "max_recall_count": 3,
        "expires_at": None,
        # origin field marks this as a PR32 signal
        "origin": "sensitive_signal",
        "signal_family": "dependency_escalation",
    }


def test_sensitive_signal_origin_is_rejected_by_admission() -> None:
    store = GumiContinuityStore()
    policy = ContinuityAdmissionPolicy(store=store)
    candidate = _make_sensitive_signal_candidate()
    decision = policy.evaluate_marker(candidate)
    assert not decision.admitted, (
        "sensitive_signal origin must be rejected at admission"
    )
    assert decision.blocked_by == "sensitive_signal_origin", (
        f"expected blocked_by='sensitive_signal_origin', got '{decision.blocked_by}'"
    )


def test_sensitive_signal_does_not_appear_in_admitted_list() -> None:
    store = GumiContinuityStore()
    policy = ContinuityAdmissionPolicy(store=store)
    normal = {
        "marker_id": "m-001",
        "subject_id": "subj-1",
        "gumi_instance_id": "gumi-1",
        "hermes_profile_id": "hermes-1",
        "status": "active",
        "gumi_recall_allowed": True,
        "recall_count": 0,
        "max_recall_count": 3,
        "expires_at": None,
    }
    signal = _make_sensitive_signal_candidate()
    admitted = policy.filter_admitted_markers([normal, signal])
    ids = {m["marker_id"] for m in admitted}
    assert "m-001" in ids
    assert "sig-001" not in ids, "sensitive_signal must not appear in admitted markers"
