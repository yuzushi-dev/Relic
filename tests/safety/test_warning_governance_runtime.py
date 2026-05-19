"""Tests for warning tier governance and Hermes safety aggregation."""

from __future__ import annotations

import json
import importlib.util
from pathlib import Path
from unittest.mock import patch


def _load_hooks_module():
    path = Path(__file__).parents[2] / "hermes-plugin" / "tools" / "relic_shared_continuity" / "hooks.py"
    spec = importlib.util.spec_from_file_location("relic_shared_continuity_hooks_under_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_hooks_adapter_module():
    path = Path(__file__).parents[2] / "hermes-plugin" / "tools" / "relic_shared_continuity" / "hooks_adapter.py"
    spec = importlib.util.spec_from_file_location("relic_shared_continuity_hooks_adapter_under_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_single_non_crisis_signal_is_not_notified() -> None:
    """Hermes safety scan queues one non-crisis event without external notification."""
    from relic.safety.signal_aggregator import InMemorySafetySignalAggregator

    hooks = _load_hooks_module()
    aggregator = InMemorySafetySignalAggregator()

    with patch.object(hooks, "_SAFETY_AGGREGATOR", aggregator):
        with patch("relic.safety.escalation_notifier.notify_escalation") as notify:
            hooks._run_safety_scan(
                subject_id="s1",
                user_message="I can't sleep and I have no energy",
                session_id="sess1",
            )

    notify.assert_not_called()


def test_single_non_crisis_signal_writes_redacted_audit(tmp_path: Path) -> None:
    """Queued non-crisis signals must have durable redacted audit records."""
    from relic.safety.signal_aggregator import InMemorySafetySignalAggregator

    hooks = _load_hooks_module()
    aggregator = InMemorySafetySignalAggregator()
    audit_path = tmp_path / "safety_signal_log.jsonl"

    with patch.object(hooks, "_SAFETY_AGGREGATOR", aggregator):
        with patch("relic.safety.signal_audit._audit_path", return_value=audit_path):
            hooks._run_safety_scan(
                subject_id="s1",
                user_message="I can't sleep and I have no energy",
                session_id="sess1",
            )

    entry = json.loads(audit_path.read_text(encoding="utf-8").strip())
    assert entry["subject_id"] == "s1"
    assert entry["signal_type"] == "sleep_energy_context"
    assert entry["warning_tier"] == "T1_context"
    assert entry["disposition"] == "queued"
    assert entry["evidence_refs"]
    assert "raw_text" not in entry
    assert "can't sleep" not in json.dumps(entry)


def test_repeated_non_crisis_signal_notifies_after_aggregation() -> None:
    """Repeated non-crisis signals notify only after multi-turn aggregation."""
    from relic.safety.signal_aggregator import InMemorySafetySignalAggregator

    hooks = _load_hooks_module()
    aggregator = InMemorySafetySignalAggregator()

    with patch.object(hooks, "_SAFETY_AGGREGATOR", aggregator):
        with patch("relic.safety.escalation_notifier.notify_escalation") as notify:
            hooks._run_safety_scan(
                subject_id="s1",
                user_message="I can't sleep and I have no energy",
                session_id="sess1",
            )
            hooks._run_safety_scan(
                subject_id="s1",
                user_message="I still can't sleep and I am so tired",
                session_id="sess2",
            )

    notify.assert_called_once()
    args, kwargs = notify.call_args
    assert args[:2] == ("s1", "sleep_energy_context")
    assert kwargs["warning_tier"] == "T2_review"
    assert kwargs["confidence"] == 0.55
    assert len(kwargs["evidence_refs"]) == 2


def test_repeated_non_crisis_signal_in_same_session_uses_distinct_redacted_refs() -> None:
    """Multiple turns in one Hermes session must still aggregate."""
    from relic.safety.signal_aggregator import InMemorySafetySignalAggregator

    hooks = _load_hooks_module()
    aggregator = InMemorySafetySignalAggregator()

    with patch.object(hooks, "_SAFETY_AGGREGATOR", aggregator):
        with patch("relic.safety.escalation_notifier.notify_escalation") as notify:
            hooks._run_safety_scan(
                subject_id="s1",
                user_message="I can't sleep and I have no energy",
                session_id="same-session",
            )
            hooks._run_safety_scan(
                subject_id="s1",
                user_message="I still can't sleep and I am so tired",
                session_id="same-session",
            )

    notify.assert_called_once()
    args, kwargs = notify.call_args
    assert args[:2] == ("s1", "sleep_energy_context")
    assert kwargs["warning_tier"] == "T2_review"
    assert kwargs["confidence"] == 0.55
    assert len(kwargs["evidence_refs"]) == 2


def test_crisis_signal_bypasses_aggregation_and_notifies_immediately() -> None:
    """Crisis signals remain immediate and do not wait for recurrence."""
    from relic.safety.signal_aggregator import InMemorySafetySignalAggregator

    hooks = _load_hooks_module()
    aggregator = InMemorySafetySignalAggregator()

    with patch.object(hooks, "_SAFETY_AGGREGATOR", aggregator):
        with patch("relic.safety.escalation_notifier.notify_escalation") as notify:
            hooks._run_safety_scan(
                subject_id="s1",
                user_message="I want to kill myself",
                session_id="sess1",
            )

    notify.assert_called_once()
    args, kwargs = notify.call_args
    assert args[:2] == ("s1", "crisis_language")
    assert kwargs["warning_tier"] == "T4_crisis"
    assert kwargs["confidence"] == 0.85
    assert len(kwargs["evidence_refs"]) == 1


def test_redacted_event_refs_do_not_expose_session_id_and_do_not_dedupe_identical_messages() -> None:
    """Evidence refs must be opaque and unique enough for repeated identical turns."""
    hooks = _load_hooks_module()

    first = hooks._redacted_event_ref("I can't sleep")
    second = hooks._redacted_event_ref("I can't sleep")

    assert "real-session-key" not in first
    assert first.startswith("turn-")
    assert first != second


def test_escalation_audit_written_even_without_contacts(tmp_path: Path) -> None:
    """Escalation audit is durable even when no contact transport is configured."""
    from relic.safety import escalation_notifier

    audit_path = tmp_path / "escalation_log.jsonl"
    with patch("relic.safety.escalation_notifier._load_escalation_contacts", return_value=[]):
        with patch("relic.safety.escalation_notifier._escalation_audit_path", return_value=audit_path):
            result = escalation_notifier.notify_escalation(
                "s1",
                "sleep_energy_context",
                evidence_refs=["sess1-turn-ref"],
                warning_tier="T2_review",
                confidence=0.55,
            )

    assert result == []
    entry = json.loads(audit_path.read_text(encoding="utf-8").strip())
    assert entry["delivery_status"] == "no_contacts"
    assert entry["evidence_refs"] == ["sess1-turn-ref"]
    assert entry["warning_tier"] == "T2_review"
    assert entry["confidence"] == 0.55


def test_adapter_repeated_non_crisis_signal_notifies_after_aggregation(tmp_path: Path) -> None:
    """Adapter hook path uses the same aggregation/audit semantics."""
    from types import SimpleNamespace

    from relic.safety.signal_aggregator import InMemorySafetySignalAggregator

    hooks_adapter = _load_hooks_adapter_module()
    envelope = SimpleNamespace(
        subject_ref="s1",
        gumi_instance_id="g1",
        hermes_profile_id="h1",
        session_id="same-session",
    )
    aggregator = InMemorySafetySignalAggregator()
    audit_path = tmp_path / "safety_signal_log.jsonl"

    with patch.object(hooks_adapter, "_SAFETY_AGGREGATOR", aggregator):
        with patch("relic.safety.signal_audit._audit_path", return_value=audit_path):
            with patch("relic.safety.escalation_notifier.notify_escalation") as notify:
                hooks_adapter._run_safety_scan_adapter(
                    envelope=envelope,
                    user_message="I can't sleep and I have no energy",
                )
                hooks_adapter._run_safety_scan_adapter(
                    envelope=envelope,
                    user_message="I still can't sleep and I am so tired",
                )

    notify.assert_called_once()
    args, kwargs = notify.call_args
    assert args[:2] == ("s1", "sleep_energy_context")
    assert kwargs["warning_tier"] == "T2_review"
    assert kwargs["confidence"] == 0.55
    assert len(audit_path.read_text(encoding="utf-8").strip().splitlines()) == 2
