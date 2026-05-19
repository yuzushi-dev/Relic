"""S2 privacy warnings are audit/workbench items, not urgent escalation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch


def test_s2_overpersonalization_warning_does_not_notify_escalation(tmp_path: Path) -> None:
    from relic.persistence import MemoryPersistence, PrivacyLevel
    from relic.privacy_gate import FinalOutputPrivacyGate

    gate = FinalOutputPrivacyGate(persistence=MemoryPersistence(tmp_path / "trace.jsonl"))
    trace = gate.scan_input("prompt", "safe draft")

    output = "I me my mine myself we us our ours I me my mine myself enough words here"
    with patch("relic.safety.escalation_notifier.notify_escalation") as notify:
        allowed, final_trace = gate.scan_final_output(output, trace.trace_id)

    assert allowed is True
    assert final_trace.privacy_level == PrivacyLevel.S2_WARNING
    assert final_trace.policy_applied == "warn_s2_overpersonalization"
    notify.assert_not_called()
