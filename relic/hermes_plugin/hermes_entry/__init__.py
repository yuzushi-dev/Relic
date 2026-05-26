from __future__ import annotations

import importlib
import importlib.util
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[3]

inject_context = None
RelicMemoryProvider = None
sanitize_for_subject = None


def _ensure_repo_on_syspath() -> None:
    if importlib.util.find_spec("relic") is not None:
        return
    repo_root = str(_REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)


def _load_relic_dependencies() -> None:
    global inject_context, RelicMemoryProvider, sanitize_for_subject

    if inject_context is None:
        inject_context = importlib.import_module(
            "relic.hermes_plugin.context_injection"
        ).inject_context
    if RelicMemoryProvider is None:
        RelicMemoryProvider = importlib.import_module(
            "relic.hermes_plugin.memory_provider"
        ).RelicMemoryProvider
    if sanitize_for_subject is None:
        sanitize_for_subject = importlib.import_module(
            "relic.gumi_plugin.output_sanitizer"
        ).sanitize_for_subject


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return value if isinstance(value, str) else str(value)


def _resolve_subject_id() -> str:
    subject_id = os.environ.get("RELIC_SUBJECT_ID", "").strip()
    if subject_id:
        return subject_id

    try:
        from hermes_cli.config import load_config

        config = load_config() or {}
        return _safe_text(config.get("subject_id")).strip()
    except Exception:
        return ""


def _resolve_profile_name() -> str:
    profile_name = os.environ.get("HERMES_PROFILE", "").strip()
    if profile_name:
        return profile_name

    try:
        from hermes_cli.config import load_config

        config = load_config() or {}
        profile_name = _safe_text(config.get("profile_name")).strip()
        if profile_name:
            return profile_name
    except Exception:
        pass

    try:
        from hermes_cli.profiles import get_active_profile_name

        return _safe_text(get_active_profile_name()).strip()
    except Exception:
        return ""


@contextmanager
def _subject_env(subject_id: str):
    previous = os.environ.get("RELIC_SUBJECT_ID")
    if not previous and subject_id:
        os.environ["RELIC_SUBJECT_ID"] = subject_id
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("RELIC_SUBJECT_ID", None)
        else:
            os.environ["RELIC_SUBJECT_ID"] = previous


def _build_memory_provider(subject_id: str, profile_name: str) -> Any | None:
    try:
        return RelicMemoryProvider(
            subject_id=subject_id,
            hermes_profile_id=profile_name or None,
            relic_home=os.environ.get("RELIC_HOME"),
        )
    except Exception:
        return None


def _normalize_context_result(result: Any) -> str:
    if isinstance(result, dict):
        return _safe_text(result.get("context")).strip()
    if isinstance(result, str):
        return result.strip()
    return ""


def _critic_replacement(response_text: str) -> str | None:
    try:
        from relic.gumi_plugin.critic import OutputCritic

        verdict = OutputCritic().review(response_text, consensual=True)
    except Exception:
        return None

    if verdict.allow:
        return None
    if verdict.reason == "false_physical_experience":
        return "[SILENT]"
    return "I'm here with you in this. What would feel most helpful right now?"


def register(ctx) -> None:
    try:
        _ensure_repo_on_syspath()
        subject_id = _resolve_subject_id()
        if not subject_id:
            return

        _load_relic_dependencies()
        profile_name = _resolve_profile_name()
        provider = _build_memory_provider(subject_id, profile_name)

        def _pre_llm_call(**kwargs: Any) -> dict[str, str] | None:
            try:
                user_message = _safe_text(kwargs.get("user_message"))
                session_id = _safe_text(kwargs.get("session_id"))
                inject_kwargs = dict(kwargs)
                inject_kwargs.pop("session_id", None)
                inject_kwargs.pop("user_message", None)
                context_parts: list[str] = []

                if provider is not None:
                    memory_text = _safe_text(provider.prefetch(user_message)).strip()
                    if memory_text:
                        context_parts.append(memory_text)

                with _subject_env(subject_id):
                    injected = inject_context(
                        session_id=session_id,
                        user_message=user_message,
                        **inject_kwargs,
                    )
                injected_text = _normalize_context_result(injected)
                if injected_text:
                    context_parts.append(injected_text)

                if not context_parts:
                    return None
                return {"context": "\n\n".join(context_parts)}
            except Exception:
                return None

        def _post_llm_call(**kwargs: Any) -> None:
            try:
                if provider is None:
                    return None
                provider.sync_turn(
                    _safe_text(kwargs.get("user_message")),
                    _safe_text(kwargs.get("assistant_response")),
                )
            except Exception:
                return None
            return None

        def _transform_llm_output(**kwargs: Any) -> str | None:
            try:
                response_text = _safe_text(kwargs.get("response_text"))
                if not response_text:
                    return None
                replacement = _critic_replacement(response_text)
                if replacement is not None:
                    return replacement
                sanitized = sanitize_for_subject(response_text)
                if sanitized is None or sanitized == response_text:
                    return None
                return sanitized
            except Exception:
                return None

        ctx.register_hook("pre_llm_call", _pre_llm_call)
        ctx.register_hook("post_llm_call", _post_llm_call)
        ctx.register_hook("transform_llm_output", _transform_llm_output)
    except Exception:
        return
