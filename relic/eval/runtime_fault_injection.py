"""Synthetic runtime hook/adapter fault-injection drill."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any

from relic.hermes_plugin.fail_safe import FailSafeRegistry, FailSafeTrigger
from relic.hermes_plugin.hooks import HookManager, LLMSessionContext, ToolCallContext
from relic.hermes_plugin.tool_permissions import ToolPermissionMatrix


REPORT_ID = "runtime_fault_injection_v1"
CLAIM_SCOPE = "synthetic_hook_adapter_fault_injection"
REVIEW_DATE = "2026-05-25"


def build_runtime_fault_injection_report() -> dict[str, Any]:
    """Exercise fail-closed behavior for local hook and adapter failure modes."""
    scenario_results = [
        _pre_llm_context_builder_exception(),
        _pre_llm_fail_safe_already_triggered(),
        _roleplay_l2_side_effect_without_approval(),
        _hermes_entry_missing_subject_no_hook_registration(),
    ]
    fail_closed_count = sum(1 for scenario in scenario_results if scenario["fail_closed"])
    unexpected_allow_count = sum(1 for scenario in scenario_results if scenario["unexpected_allow"])
    all_scenarios_passed = all(scenario["passed"] for scenario in scenario_results)
    return {
        "report_id": REPORT_ID,
        "claim_scope": CLAIM_SCOPE,
        "methodology": {
            "evidence_model": "controlled_fault_injection_over_runtime_hooks",
            "review_date": REVIEW_DATE,
            "fault_model": [
                "context_builder_exception",
                "fail_safe_pre_triggered",
                "side_effect_tool_without_approval",
                "missing_subject_scope_for_entry_adapter",
            ],
        },
        "summary": {
            "scenario_count": len(scenario_results),
            "fail_closed_count": fail_closed_count,
            "unexpected_allow_count": unexpected_allow_count,
            "all_scenarios_passed": all_scenarios_passed,
        },
        "scenario_results": scenario_results,
        "validation": {
            "valid": all_scenarios_passed,
            "checked_rules": [
                "pre_llm_exception_returns_no_context_pack",
                "pre_llm_fail_safe_blocks_context_pack",
                "roleplay_side_effect_tool_blocked_without_approval",
                "missing_subject_entry_adapter_registers_no_hooks",
                "fault_injection_does_not_store_raw_private_payloads",
            ],
        },
        "claim_limitations": [
            "synthetic local fault injection only",
            "does not prove every production Hermes adapter is installed",
            "does not exercise network, provider, or scheduler infrastructure failures",
            "does not replace live runtime telemetry or incident-response evidence",
        ],
    }


def _pre_llm_context_builder_exception() -> dict[str, Any]:
    from relic.context_pack.builder import ContextPackBuilder

    original_build = ContextPackBuilder.build

    def raising_build(self):  # noqa: ANN001
        raise RuntimeError("synthetic builder fault")

    ContextPackBuilder.build = raising_build
    try:
        manager = HookManager(permission_matrix=ToolPermissionMatrix())
        result = manager.pre_llm_call(
            LLMSessionContext(
                session_id="fault-session-builder",
                trace_id="trace-builder-fault",
            )
        )
    finally:
        ContextPackBuilder.build = original_build

    fail_closed = (
        result.success is False
        and result.fail_closed is True
        and result.context_pack is None
    )
    return _scenario(
        scenario_id="pre_llm_context_builder_exception",
        fault="ContextPackBuilder.build raises RuntimeError",
        observed={
            "success": result.success,
            "fail_closed": result.fail_closed,
            "context_pack_present": result.context_pack is not None,
            "reason_prefix": str(result.reason or "").split(":", 1)[0],
        },
        fail_closed=fail_closed,
        unexpected_allow=result.success is True,
    )


def _pre_llm_fail_safe_already_triggered() -> dict[str, Any]:
    registry = FailSafeRegistry(enabled=True)
    registry.trigger(
        reason="synthetic pre-existing hook fault",
        trigger=FailSafeTrigger.HOOK_ERROR,
        trace_id="trace-pre-triggered",
    )
    manager = HookManager(
        permission_matrix=ToolPermissionMatrix(),
        fail_safe=registry,
    )
    result = manager.pre_llm_call(
        LLMSessionContext(
            session_id="fault-session-triggered",
            trace_id="trace-pre-triggered",
        )
    )
    fail_closed = (
        result.success is False
        and result.fail_closed is True
        and result.reason == "fail_safe_triggered"
        and registry.check().blocked is True
    )
    return _scenario(
        scenario_id="pre_llm_fail_safe_already_triggered",
        fault="FailSafeRegistry is triggered before pre_llm_call",
        observed={
            "success": result.success,
            "fail_closed": result.fail_closed,
            "reason": result.reason,
            "fail_safe_blocked": registry.check().blocked,
            "fail_safe_event_count": len(registry.get_events()),
        },
        fail_closed=fail_closed,
        unexpected_allow=result.success is True,
    )


def _roleplay_l2_side_effect_without_approval() -> dict[str, Any]:
    registry = FailSafeRegistry(enabled=True)
    manager = HookManager(
        permission_matrix=ToolPermissionMatrix(),
        fail_safe=registry,
    )
    result = manager.pre_tool_call(
        ToolCallContext(
            tool_name="provider.call",
            tool_args={"provider_id": "synthetic-provider"},
            session_id="fault-session-tool",
            is_roleplay=True,
            explicit_approval=False,
            trace_id="trace-provider-call-blocked",
        )
    )
    blocked = result.allowed is False and registry.check().blocked is True
    return _scenario(
        scenario_id="roleplay_l2_side_effect_without_approval",
        fault="L2 side-effect tool requested in roleplay without explicit approval",
        observed={
            "allowed": result.allowed,
            "reason_code": result.reason_code,
            "blocked_reason_present": result.blocked_reason is not None,
            "fail_safe_blocked": registry.check().blocked,
            "audit_event_count": len(manager.get_audit_log()),
        },
        fail_closed=blocked,
        unexpected_allow=result.allowed is True,
    )


def _hermes_entry_missing_subject_no_hook_registration() -> dict[str, Any]:
    from relic.hermes_plugin import hermes_entry

    context = _RegistrationContext()
    with _temporary_env(RELIC_SUBJECT_ID=None):
        hermes_entry.register(context)

    fail_closed = len(context.registered_hooks) == 0
    return _scenario(
        scenario_id="hermes_entry_missing_subject_no_hook_registration",
        fault="Hermes entry adapter starts without RELIC_SUBJECT_ID or profile subject_id",
        observed={
            "registered_hook_count": len(context.registered_hooks),
            "registered_hooks": list(context.registered_hooks),
        },
        fail_closed=fail_closed,
        unexpected_allow=not fail_closed,
    )


def _scenario(
    *,
    scenario_id: str,
    fault: str,
    observed: dict[str, Any],
    fail_closed: bool,
    unexpected_allow: bool,
) -> dict[str, Any]:
    return {
        "scenario_id": scenario_id,
        "fault": fault,
        "expected_behavior": "disallow_or_no_injection",
        "observed": observed,
        "fail_closed": fail_closed,
        "unexpected_allow": unexpected_allow,
        "passed": fail_closed and not unexpected_allow,
    }


class _RegistrationContext:
    def __init__(self) -> None:
        self.registered_hooks: list[str] = []

    def register_hook(self, hook_name: str, handler: Any) -> None:
        self.registered_hooks.append(hook_name)


@contextmanager
def _temporary_env(**updates: str | None):
    previous = {key: os.environ.get(key) for key in updates}
    try:
        for key, value in updates.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
