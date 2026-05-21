from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest


class FakeContext:
    def __init__(self) -> None:
        self.hooks: list[tuple[str, object]] = []

    def register_hook(self, hook_name: str, callback: object) -> None:
        self.hooks.append((hook_name, callback))


def _load_entry_module():
    return importlib.import_module("relic.hermes_plugin.hermes_entry")


def test_register_records_three_hermes_hooks(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_entry_module()
    ctx = FakeContext()

    monkeypatch.setattr(module, "_ensure_repo_on_syspath", lambda: None)
    monkeypatch.setattr(module, "_resolve_subject_id", lambda: "subj-001")

    module.register(ctx)

    assert [name for name, _ in ctx.hooks] == [
        "pre_llm_call",
        "post_llm_call",
        "transform_llm_output",
    ]


def test_register_no_subject_id_is_safe_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_entry_module()
    ctx = FakeContext()

    monkeypatch.setattr(module, "_ensure_repo_on_syspath", lambda: None)
    monkeypatch.setattr(module, "_resolve_subject_id", lambda: "")

    module.register(ctx)

    assert ctx.hooks == []


def test_pre_llm_adapter_returns_context_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_entry_module()
    ctx = FakeContext()

    monkeypatch.setattr(module, "_ensure_repo_on_syspath", lambda: None)
    monkeypatch.setattr(module, "_resolve_subject_id", lambda: "subj-001")
    monkeypatch.setattr(module, "_resolve_profile_name", lambda: "gumi-subj-001")
    monkeypatch.setattr(
        module,
        "RelicMemoryProvider",
        lambda **kwargs: SimpleNamespace(prefetch=lambda query: "line one\nline two"),
    )
    monkeypatch.setattr(
        module,
        "inject_context",
        lambda **kwargs: {"context": "existing context"},
    )

    module.register(ctx)
    pre_hook = dict(ctx.hooks)["pre_llm_call"]

    result = pre_hook(
        session_id="sess-1",
        user_message="hello",
        conversation_history=[],
        is_first_turn=True,
        model="x",
        platform="telegram",
        sender_id="user-1",
    )

    assert isinstance(result, dict)
    assert "context" in result
    assert "existing context" in result["context"]
    assert "line one" in result["context"]


def test_pre_llm_adapter_never_raises_on_bad_input(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_entry_module()
    ctx = FakeContext()

    monkeypatch.setattr(module, "_ensure_repo_on_syspath", lambda: None)
    monkeypatch.setattr(module, "_resolve_subject_id", lambda: "subj-001")
    monkeypatch.setattr(module, "_resolve_profile_name", lambda: "")
    monkeypatch.setattr(
        module,
        "RelicMemoryProvider",
        lambda **kwargs: SimpleNamespace(prefetch=lambda query: (_ for _ in ()).throw(RuntimeError("boom"))),
    )
    monkeypatch.setattr(
        module,
        "inject_context",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    module.register(ctx)
    pre_hook = dict(ctx.hooks)["pre_llm_call"]

    assert pre_hook(user_message=None) is None


def test_transform_adapter_returns_string_or_none(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_entry_module()
    ctx = FakeContext()

    monkeypatch.setattr(module, "_ensure_repo_on_syspath", lambda: None)
    monkeypatch.setattr(module, "_resolve_subject_id", lambda: "subj-001")
    monkeypatch.setattr(module, "_resolve_profile_name", lambda: "")
    monkeypatch.setattr(module, "sanitize_for_subject", lambda text: "clean text")

    module.register(ctx)
    transform_hook = dict(ctx.hooks)["transform_llm_output"]

    assert transform_hook(response_text="[WARN]\nclean text") == "clean text"


def test_transform_adapter_returns_none_when_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_entry_module()
    ctx = FakeContext()

    monkeypatch.setattr(module, "_ensure_repo_on_syspath", lambda: None)
    monkeypatch.setattr(module, "_resolve_subject_id", lambda: "subj-001")
    monkeypatch.setattr(module, "_resolve_profile_name", lambda: "")
    monkeypatch.setattr(module, "sanitize_for_subject", lambda text: text)

    module.register(ctx)
    transform_hook = dict(ctx.hooks)["transform_llm_output"]

    assert transform_hook(response_text="already clean") is None


def test_post_llm_adapter_syncs_turn(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_entry_module()
    ctx = FakeContext()
    calls: list[tuple[str, str]] = []

    monkeypatch.setattr(module, "_ensure_repo_on_syspath", lambda: None)
    monkeypatch.setattr(module, "_resolve_subject_id", lambda: "subj-001")
    monkeypatch.setattr(module, "_resolve_profile_name", lambda: "gumi-subj-001")
    monkeypatch.setattr(
        module,
        "RelicMemoryProvider",
        lambda **kwargs: SimpleNamespace(
            prefetch=lambda query: "",
            sync_turn=lambda user_msg, assistant_msg: calls.append((user_msg, assistant_msg)),
        ),
    )
    monkeypatch.setattr(module, "inject_context", lambda **kwargs: None)

    module.register(ctx)
    post_hook = dict(ctx.hooks)["post_llm_call"]

    result = post_hook(user_message="ciao", assistant_response="salve")

    assert result is None
    assert calls == [("ciao", "salve")]


def test_install_helper_creates_symlink_and_is_idempotent(tmp_path: Path) -> None:
    from relic.hermes_plugin.install import install_relic_hermes_plugin

    hermes_home = tmp_path / "profile"
    plugins_home = hermes_home / "plugins"

    first = install_relic_hermes_plugin(hermes_home)
    second = install_relic_hermes_plugin(hermes_home)

    assert first["status"] == "created"
    assert second["status"] == "already_installed"
    assert first["link_path"] == second["link_path"]
    assert Path(first["link_path"]).is_symlink()
    assert Path(first["link_path"]).resolve() == (
        Path(__file__).resolve().parents[2] / "relic" / "hermes_plugin" / "hermes_entry"
    )


def test_install_helper_leaves_non_symlink_in_place(tmp_path: Path) -> None:
    from relic.hermes_plugin.install import install_relic_hermes_plugin

    hermes_home = tmp_path / "profile"
    plugins_home = hermes_home / "plugins"
    target = plugins_home / "relic"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("occupied", encoding="utf-8")

    result = install_relic_hermes_plugin(hermes_home)

    assert result["status"] == "blocked"
    assert target.read_text(encoding="utf-8") == "occupied"


def test_enable_helper_updates_plugins_allow_and_deny_lists(tmp_path: Path) -> None:
    import yaml

    from relic.hermes_plugin.install import enable_relic_hermes_plugin

    hermes_home = tmp_path / "profile"
    config_path = hermes_home / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        yaml.safe_dump(
            {
                "model": {"default": "gpt-5"},
                "plugins": {
                    "enabled": ["other"],
                    "disabled": ["relic", "legacy"],
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    first = enable_relic_hermes_plugin(hermes_home)
    second = enable_relic_hermes_plugin(hermes_home)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    assert first["status"] == "enabled"
    assert second["status"] == "already_enabled"
    assert config["plugins"]["enabled"] == ["other", "relic"]
    assert config["plugins"]["disabled"] == ["legacy"]
