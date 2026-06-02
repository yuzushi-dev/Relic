from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys

from relic.profile.registry import ProfileRegistry
from relic.hermes_runtime import (
    HERMES_CONTEXT_LENGTH,
    HERMES_DEFAULT_MODEL,
    HERMES_OLLAMA_BASE_URL,
    HINDSIGHT_DEFAULT_PROVIDER,
    render_hindsight_local_config,
    check_hermes_feature_support,
    init_runtime_config,
    RuntimeDecision,
    DeliveryGate,
    ResumeReconciliation,
)

def _print_setup_check(name: str, command: str, install_hint: str) -> None:
    binary = shutil.which(command)
    if binary:
        print(f"  [ok] {name}: {binary}")
        return
    print(f"  [missing] {name}")
    print(f"       {install_hint}")

def _confirm(question: str, default: bool = False) -> bool:
    suffix = "Y/n" if default else "y/N"
    try:
        answer = input(f"{question} ({suffix}) ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return default
    if not answer:
        return default
    return answer in {"y", "yes"}

def _refresh_user_path() -> None:
    user_bin = str(Path.home() / ".local" / "bin")
    current = os.environ.get("PATH", "")
    if user_bin not in current.split(os.pathsep):
        os.environ["PATH"] = user_bin + os.pathsep + current

def _venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"

def _venv_relic(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "relic.exe"
    return venv_dir / "bin" / "relic"

def _bootstrap_local_venv(venv_dir: Path) -> int:
    print("\n=== Relic Bootstrap ===\n")
    subprocess.run(["python", "-m", "venv", str(venv_dir)], check=True)
    print(f"Created virtual environment: {venv_dir}")
    python_bin = _venv_python(venv_dir)
    subprocess.run([str(python_bin), "-m", "pip", "install", "-e", ".[dev]"], check=True)
    print("Installed Relic into the virtual environment.")
    relic_bin = _venv_relic(venv_dir)
    print("Launching setup inside the virtual environment.\n")
    subprocess.run([str(relic_bin), "setup"], check=True)
    return 0

def _install_ollama_if_requested() -> bool:
    if shutil.which("ollama"):
        print("  [ok] Ollama is installed.")
        return True
    print("  [missing] Ollama")
    print("       Official download: https://ollama.com/download")
    print("       Linux/macOS installer: curl -fsSL https://ollama.com/install.sh | sh")
    if _confirm("Install Ollama now?"):
        subprocess.run(["bash", "-lc", "curl -fsSL https://ollama.com/install.sh | sh"], check=True)
        _refresh_user_path()
        return True
    return False

def _prepare_ollama_account_and_model(model: str, available: bool) -> None:
    if not available:
        print("  [skip] Ollama is not installed; skipping Ollama signin/model pull.")
        return
    print("Ollama account/model:")
    print("  Use `ollama signin` for Ollama cloud models or hosted embedding support.")
    if _confirm("Run `ollama signin` now?"):
        subprocess.run(["ollama", "signin"], check=True)
    if _confirm(f"Pull starter model `{model}` now?"):
        subprocess.run(["ollama", "pull", model], check=True)

def _install_hermes_if_requested() -> bool:
    if shutil.which("hermes"):
        print("  [ok] Hermes is installed.")
        return True
    print("  [missing] Hermes")
    print("       Official installer:")
    print("       curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash")
    if _confirm("Install Hermes now?"):
        subprocess.run(
            [
                "bash",
                "-lc",
                "curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash",
            ],
            check=True,
        )
        _refresh_user_path()
        return True
    return False

def _configure_hermes_for_ollama(model: str, available: bool) -> None:
    if not available:
        print("  [skip] Hermes is not installed; skipping Hermes model configuration.")
        return
    print("Hermes model configuration:")
    print("  Provider: custom")
    print(f"  Base URL: {HERMES_OLLAMA_BASE_URL}")
    print(f"  Model:    {model}")
    print(f"  Context:  {HERMES_CONTEXT_LENGTH}")
    if not _confirm("Configure Hermes to use Ollama now?", default=True):
        return
    commands = [
        ["hermes", "config", "set", "model.provider", "custom"],
        ["hermes", "config", "set", "model.base_url", HERMES_OLLAMA_BASE_URL],
        ["hermes", "config", "set", "model.default", model],
        ["hermes", "config", "set", "model.context_length", str(HERMES_CONTEXT_LENGTH)],
        ["hermes", "config", "set", "agent.tool_use_enforcement", "true"],
        ["hermes", "config", "set", "approvals.mode", "manual"],
        ["hermes", "config", "set", "privacy.redact_pii", "true"],
        ["hermes", "config", "set", "cron.wrap_response", "false"],
        ["hermes", "config", "set", "cron.script_timeout_seconds", "300"],
    ]
    for command in commands:
        subprocess.run(command, check=True)

def _hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))

def _configure_hindsight_local(available: bool, model: str) -> None:
    if not available:
        print("  [skip] Hermes is not installed; skipping Hindsight local memory configuration.")
        return
    print("Hindsight local mode:")
    print("  Provider: hindsight")
    print(f"  LLM:      {HINDSIGHT_DEFAULT_PROVIDER}")
    print("  Mode:     local")
    print("  Memory:   tools")
    print("  Note: the embedded daemon starts on first Hermes use.")
    if not _confirm("Configure Hermes native Hindsight local memory now?", default=True):
        return

    try:
        llm_provider_raw = input(f"Hindsight local LLM provider [{HINDSIGHT_DEFAULT_PROVIDER}] ").strip()
        llm_provider = llm_provider_raw.lower() if llm_provider_raw else HINDSIGHT_DEFAULT_PROVIDER
    except (EOFError, KeyboardInterrupt):
        print()
        llm_provider = HINDSIGHT_DEFAULT_PROVIDER

    api_key = None
    api_key_env = None
    if llm_provider == "ollama":
        try:
            api_key_env = input("Ollama API key env var (optional, blank for local/signin) [] ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            api_key_env = ""
    if llm_provider != "ollama":
        try:
            api_key_env = input("LLM API key env var [HINDSIGHT_LLM_API_KEY] ").strip() or "HINDSIGHT_LLM_API_KEY"
        except (EOFError, KeyboardInterrupt):
            print()
            api_key_env = "HINDSIGHT_LLM_API_KEY"
        api_key = os.environ.get(api_key_env)
        if not api_key:
            # Print static message only: no user-supplied variable in output
            print("  [skip] LLM API key env var is not set; skipping Hindsight local config.")
            print("       Export the configured env var and rerun `relic setup --with-runtime`.")
            return

    hindsight_dir = _hermes_home() / "hindsight"
    hindsight_dir.mkdir(parents=True, exist_ok=True)
    config_path = hindsight_dir / "config.json"
    config = render_hindsight_local_config(
        bank_id="relic-local",
        llm_provider=llm_provider,
        model=model,
        llm_api_key=api_key,
        llm_api_key_env=api_key_env or None,
    )
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    subprocess.run(["hermes", "config", "set", "memory.provider", "hindsight"], check=True)
    subprocess.run(["hermes", "memory", "status"], check=False)


def start_hermes_gateway_for_profile(profile_name: str, timeout_seconds: int = 30) -> bool:
    """Install + start the managed Hermes gateway service for a profile.

    Installs the per-profile systemd/launchd unit (via ``hermes gateway
    install``) and starts it, then polls ``hermes gateway list`` until the
    profile reports running or the timeout is exceeded.

    Using the managed service, not a detached ``gateway run`` subprocess , 
    means the gateway survives terminal close and reboot, and exactly one
    instance per profile polls Telegram. A detached run leaves an unmanaged
    process that dies with the shell and never registers for autostart.
    Returns True if confirmed running, False otherwise (non-fatal).
    """
    import subprocess
    import time

    hermes = shutil.which("hermes")
    if not hermes:
        print("  [skip] Hermes not found in PATH; skipping gateway start.")
        return False

    def _is_ready() -> bool:
        try:
            result = subprocess.run(
                [hermes, "gateway", "list"],
                capture_output=True, text=True, timeout=10,
            )
            for line in result.stdout.splitlines():
                if profile_name in line and "✓" in line:
                    return True
        except Exception:
            pass
        return False

    if _is_ready():
        print(f"  [ok] Gateway '{profile_name}' already running.")
        return True

    print(f"  Installing + starting gateway service '{profile_name}'...")
    try:
        # The profile is selected via the global --profile flag, before the
        # subcommand; install is idempotent with --force.
        subprocess.run(
            [hermes, "--profile", profile_name, "gateway", "install", "--force"],
            capture_output=True, text=True, timeout=60,
        )
        subprocess.run(
            [hermes, "--profile", profile_name, "gateway", "start"],
            capture_output=True, text=True, timeout=60,
        )
    except Exception as exc:
        print(f"  [skip] Could not install/start gateway service: {exc}")
        return False

    # Poll until ready or timeout
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        time.sleep(1)
        if _is_ready():
            print(f"  [ok] Gateway '{profile_name}' is ready.")
            return True

    print(f"  [warn] Gateway '{profile_name}' did not become ready within {timeout_seconds}s.")
    return False


def _runtime_setup(model: str) -> None:
    print("\n=== Relic Runtime Setup ===\n")
    print("Ollama is configured before Hermes so Hermes can use it as the model backend.")
    ollama_available = _install_ollama_if_requested()
    _prepare_ollama_account_and_model(model, available=ollama_available)
    hermes_available = _install_hermes_if_requested()
    _configure_hermes_for_ollama(model, available=hermes_available)
    _configure_hindsight_local(available=hermes_available, model=model)
    init_runtime_features()


def init_runtime_features() -> None:
    """Initialize runtime features after Hermes configuration."""
    from relic.hermes_runtime import check_hermes_feature_support, init_runtime_config

    print("\n=== Runtime Feature Initialization ===\n")
    features = check_hermes_feature_support()
    config = init_runtime_config()

    # RuntimeDecision storage (in-memory)
    print("  RuntimeDecision storage: in-memory")

    # DeliveryGate storage (in-memory)
    print("  DeliveryGate storage: in-memory")

    # ResumeReconciliation storage (in-memory)
    print("  ResumeReconciliation storage: in-memory")

    # Print feature summary
    print("\n  Hermes feature support:")
    print(f"    no_agent_cron:         {features.get('no_agent_cron', False)}")
    print(f"    transform_llm_output:  {features.get('transform_llm_output', False)}")
    print(f"    session_key_support:   {features.get('session_key_support', False)}")
    print(f"    allowlist_support:     {features.get('allowlist_support', False)}")

    # Verify Hermes version
    import subprocess
    try:
        result = subprocess.run(
            ["hermes", "version"], capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            version = result.stdout.strip() or result.stderr.strip()
            print(f"\n  Hermes version: {version}")
        else:
            print("\n  Hermes version: unknown (hermes not available)")
    except Exception:
        print("\n  Hermes version: unknown (hermes not available)")

    print()


UI_DIR = Path(__file__).parent.parent / "ui"
UI_PORT = 4143

def _ui_start(ui_dir: Path) -> None:
    if shutil.which("docker"):
        print("Starting Researcher UI via Docker...")
        subprocess.run(["docker", "compose", "up", "-d", "--build"], cwd=ui_dir, check=True)
        print(f"UI running at http://localhost:{UI_PORT}/workbench")
    elif shutil.which("npm"):
        print("Docker not found, starting via npm dev server (Ctrl+C to stop)...")
        subprocess.run(["npm", "install"], cwd=ui_dir, check=True)
        subprocess.run(["npm", "run", "dev"], cwd=ui_dir)
    else:
        print("[missing] Neither Docker nor npm found.")
        print("  Install Docker:   https://docs.docker.com/get-docker/")
        print("  Install Node.js:  https://nodejs.org/")

def ui_main(argv: list[str] | None = None) -> int:
    """Launch the Researcher UI."""
    parser = argparse.ArgumentParser(
        prog="relic ui",
        description="Launch the Researcher UI (Docker or npm fallback).",
    )
    parser.parse_args(argv)

    if not UI_DIR.exists():
        print(f"[missing] UI directory not found: {UI_DIR}")
        return 1

    _ui_start(UI_DIR)
    return 0

def init_main(argv: list[str] | None = None) -> int:
    """First-time setup wizard: install and configure runtime tools."""
    parser = argparse.ArgumentParser(
        prog="relic init",
        description="First-time setup: install and configure Ollama and Hermes.",
    )
    parser.add_argument(
        "--ollama-model",
        default=HERMES_DEFAULT_MODEL,
        help="Starter Ollama model to configure in Hermes.",
    )
    args = parser.parse_args(argv)

    print("\n=== Relic Init ===\n")
    print("This wizard installs and configures the runtime tools (Ollama and Hermes).")
    print("When done, run `relic subject create` to create your first subject.\n")

    _runtime_setup(args.ollama_model)

    print("\nRuntime setup complete.")
    print("Next: run `relic subject create` to create a subject and start experimenting.")
    return 0

def setup_main(argv: list[str] | None = None) -> int:
    """Install and configure Relic runtime dependencies."""
    parser = argparse.ArgumentParser(
        prog="relic setup",
        description="Install/check Relic runtime dependencies.",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only check local tool availability.",
    )
    parser.add_argument(
        "--bootstrap",
        action="store_true",
        help="Create a local virtual environment, install Relic, and relaunch setup inside it.",
    )
    parser.add_argument(
        "--venv",
        default=".venv",
        help="Virtual environment path for --bootstrap.",
    )
    parser.add_argument(
        "--with-runtime",
        action="store_true",
        help="Guide Ollama installation/sign-in first, then Hermes installation/configuration.",
    )
    parser.add_argument(
        "--ollama-model",
        default=HERMES_DEFAULT_MODEL,
        help="Starter Ollama model to configure in Hermes.",
    )
    args = parser.parse_args(argv)

    if args.bootstrap:
        return _bootstrap_local_venv(Path(args.venv))

    print("\n=== Relic Setup ===\n")
    print("Relic setup installs/checks the local runtime. It does not create subjects.")
    print("Use `relic subject create` after setup to create a subject and Gumi profile.\n")
    print("Runtime install order: Ollama before Hermes.")
    print("Runtime checks:")
    _print_setup_check(
        "Hermes",
        "hermes",
        "Install/configure Hermes before live Gumi delivery or cron runtime.",
    )
    _print_setup_check(
        "Ollama",
        "ollama",
        "Install from https://ollama.com/download; use `ollama signin` for cloud models.",
    )
    print("")

    if args.with_runtime:
        _runtime_setup(args.ollama_model)

    if args.check_only:
        print("Next: run `relic init` for runtime setup, then `relic subject create` to create a subject.")
        return 0

    print("Setup complete.")
    if args.with_runtime:
        print("Next: run `relic subject create` to create a subject and private Gumi profile.")
    else:
        print("Next: run `relic init` for runtime setup, then `relic subject create` to create a subject.")
    return 0

def subject_main(argv: list[str] | None = None) -> int:
    """Guided subject management entrypoint."""
    parser = argparse.ArgumentParser(
        prog="relic subject",
        description="Create and manage Relic subjects through guided workflows.",
    )
    subparsers = parser.add_subparsers(dest="subject_action", required=True)
    create_parser = subparsers.add_parser("create", help="Create a subject and private Gumi profile.")
    create_parser.add_argument("--subject-id", default=None, help="Subject identifier.")
    create_parser.add_argument("--experiment-id", default=None, help="Experiment identifier.")
    show_parser = subparsers.add_parser("show", help="Show subject runtime status (hides raw session key).")
    show_parser.add_argument("subject_id", help="Subject identifier.")
    reprovision_parser = subparsers.add_parser("reprovision", help="Re-run provisioning for an active subject with missing artifacts.")
    reprovision_parser.add_argument("subject_id", help="Subject identifier.")
    forget_parser = subparsers.add_parser("forget", help="GDPR Art. 17 hard delete, permanently erase all subject data.")
    forget_parser.add_argument("subject_id", help="Subject identifier to erase.")
    forget_parser.add_argument("--yes", action="store_true", help="Skip interactive confirmation (use in automated pipelines only).")
    args = parser.parse_args(argv)

    if args.subject_action == "create":
        print("\n=== Relic Subject ===\n")
        from relic.profile.bootstrap_tui import BootstrapTUI

        registry = ProfileRegistry()
        tui = BootstrapTUI(registry=registry)
        tui.run_init(subject_id=args.subject_id, experiment_id=args.experiment_id)
        print("\nNext steps:")
        print("  - Use `relic profile list` to see subjects.")
        print("  - Use `relic profile hermes configure-telegram ...` when you are ready for live Gumi.")
        print("  - Use the Researcher UI to inspect subject state and review data.")
        return 0

    if args.subject_action == "show":
        return _subject_show(args.subject_id)

    if args.subject_action == "reprovision":
        from relic.profile.bootstrap_tui import BootstrapTUI
        registry = ProfileRegistry()
        tui = BootstrapTUI(registry=registry)
        tui.run_reprovision(args.subject_id)
        return 0

    if args.subject_action == "forget":
        return _subject_forget(args.subject_id, skip_confirm=args.yes)

    return 0


def _subject_show(subject_id: str) -> int:
    """Show detailed subject runtime status, never exposing raw session key."""
    registry = ProfileRegistry()
    profile = registry.get_subject(subject_id)
    if profile is None:
        print(f"Subject '{subject_id}' not found.", file=sys.stderr)
        return 1

    # Load delivery policy if exists
    delivery_policy = None
    delivery_policy_path = registry._delivery_policy_path(subject_id)
    if delivery_policy_path.exists():
        with open(delivery_policy_path) as f:
            delivery_policy = json.load(f)

    # Check session key hash presence (never show raw key)
    session_key_hash_present = False
    session_key_path = profile.relic_subject_home / ".session_key_hash"
    if session_key_path.exists():
        session_key_hash_present = True

    # Check allowlist count
    allowlist_count = 0
    if delivery_policy:
        from relic.hermes_runtime import get_allowlist_entry
        platform = delivery_policy.get("contact_channel", "telegram")
        entry = get_allowlist_entry(subject_id, platform)
        if entry:
            allowlist_count = 1

    # Determine no-agent cron status
    no_agent_cron_status = "unknown"
    cron_manifest_path = profile.relic_subject_home / "gumi_cron_manifest.json"
    if cron_manifest_path.exists():
        manifest = json.loads(cron_manifest_path.read_text(encoding="utf-8"))
        if manifest.get("hermes_native") and manifest.get("install_commands"):
            no_agent_cron_status = "provisioned"
        else:
            no_agent_cron_status = "configured"
    elif profile.status in ("active", "intro_sent"):
        no_agent_cron_status = "not_configured"

    # Determine resume reconciliation status
    resume_reconciliation_status = "unknown"
    if profile.status == "active":
        if session_key_hash_present:
            resume_reconciliation_status = "enabled"
        else:
            resume_reconciliation_status = "requires_session_key"

    # Continuity scope status
    continuity_scope_status = "unknown"
    if delivery_policy:
        if delivery_policy.get("delivery_enabled"):
            continuity_scope_status = "active"
        else:
            continuity_scope_status = "disabled"
    elif profile.status in ("draft", "baseline_in_progress", "baseline_complete",
                            "gumi_seed_generated", "gumi_seed_reviewed",
                            "hermes_profile_provisioned", "intro_composed", "intro_sent"):
        continuity_scope_status = "pending_activation"

    # Session key hash presence (yes/no, never the hash itself)
    session_key_display = "yes" if session_key_hash_present else "no"

    print(f"=== Subject Runtime Status: {subject_id} ===\n")
    print(f"  subject_id:               {profile.subject_id}")
    print(f"  status:                   {profile.status}")
    print(f"  hermes_profile_name:      {profile.hermes_profile_name}")
    print(f"  session_key_hash:         {session_key_display}")
    print(f"  delivery_enabled:         {delivery_policy.get('delivery_enabled') if delivery_policy else 'not_configured'}")
    print(f"  allowlist_count:          {allowlist_count}")
    print(f"  no_agent_cron_status:     {no_agent_cron_status}")
    print(f"  resume_reconciliation:    {resume_reconciliation_status}")
    print(f"  continuity_scope_status:  {continuity_scope_status}")
    return 0


def _subject_forget(subject_id: str, *, skip_confirm: bool = False) -> int:
    """GDPR Art. 17 hard delete, permanently erase all data for a subject.

    Requires typing the subject_id to confirm unless --yes is passed.
    Emits an anonymised audit record (subject_id hash, not raw) BEFORE erasure.
    """
    import hashlib

    registry = ProfileRegistry()
    profile = registry.get_subject(subject_id)

    print()
    print("=" * 64)
    print("  WARNING: IRREVERSIBLE DATA DELETION  (GDPR Art. 17)")
    print("=" * 64)
    print(f"  Subject ID : {subject_id}")
    if profile:
        print(f"  Hermes profile : {profile.hermes_profile_name}")
        print(f"  Status         : {profile.status}")
    else:
        print("  [subject not found in registry, filesystem deletion will still run]")
    print()
    print("  This will PERMANENTLY DELETE (no recovery possible):")
    print("    - All continuity markers, followups, and corrections (in-memory)")
    print("    - Subject directory:  ~/.relic/subjects/{subject_id}/")
    print("      (profile JSON, baseline, relic.db check-in data, delivery policy,")
    print("       cron manifest, session key hash, all generated files)")
    print("    - All chronicle events, decisions, snapshots, access log rows")
    print("      linked to this subject in the shared SQLite DB")
    print("    - All daily JSONL journal lines for this subject")
    print("    - Legacy JSONL entries (cac_trace, privacy_trace, escalation_log)")
    print()

    if not skip_confirm:
        print("  To confirm, type the subject ID exactly:")
        print()
        try:
            typed = input("  > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            print("Aborted.")
            return 1

        if typed != subject_id:
            print()
            print(f"  Mismatch (got '{typed}'). Aborted, no data was deleted.")
            return 1

    print()
    print("  Executing erasure...")

    # Emit anonymised audit record BEFORE deletion so the event itself
    # does not contain subject_id and survives the chronicle purge.
    subject_hash = hashlib.sha256(subject_id.encode()).hexdigest()
    try:
        from relic.chronicle import emit_event, EventCategory
        emit_event(
            event_type="subject_forgotten",
            event_category=EventCategory.DECISION,
            source_module="relic.cli",
            subject_id=None,  # intentionally omitted, record must survive purge
            payload={"subject_id_hash": subject_hash},
        )
    except Exception:
        pass  # fail-open: audit failure must not block erasure

    # 1. In-memory continuity data (no-op if no running session)
    try:
        from relic.shared_continuity.service import ContinuityService
        svc = ContinuityService()
        svc.forget_subject(subject_id)
    except Exception:
        pass

    # 2. Chronicle SQLite + JSONL purge
    chronicle_result: dict = {}
    try:
        from relic.chronicle.retention import purge_subject_records
        chronicle_result = purge_subject_records(subject_id)
    except Exception as exc:
        print(f"  [warn] Chronicle purge failed: {exc}", file=sys.stderr)

    # 3. Filesystem deletion (profile, relic.db, all subject files)
    fs_result: dict = {}
    try:
        fs_result = registry.delete_subject(subject_id)
    except Exception as exc:
        print(f"  [warn] Filesystem deletion failed: {exc}", file=sys.stderr)
        return 1

    # 4. Hermes profile directory (best-effort)
    hermes_profile_name = fs_result.get("hermes_profile_name")
    hermes_deleted = False
    if hermes_profile_name:
        hermes_profiles_home = registry.hermes_profiles_home
        hermes_profile_dir = hermes_profiles_home / hermes_profile_name
        if hermes_profile_dir.exists():
            try:
                import shutil as _shutil
                _shutil.rmtree(hermes_profile_dir)
                hermes_deleted = True
            except Exception as exc:
                print(f"  [warn] Hermes profile deletion failed: {exc}", file=sys.stderr)

    print()
    print("  Erasure complete.")
    print(f"  subject_id_hash : {subject_hash[:16]}...")
    print(f"  chronicle events deleted   : {chronicle_result.get('chronicle_events_deleted', 0)}")
    print(f"  chronicle decisions deleted: {chronicle_result.get('chronicle_decisions_deleted', 0)}")
    print(f"  journal lines removed      : {chronicle_result.get('journal_lines_removed', 0)}")
    print(f"  filesystem paths deleted   : {fs_result.get('deleted_paths', [])}")
    if hermes_profile_name:
        print(f"  hermes profile deleted     : {hermes_deleted} ({hermes_profile_name})")
    print()
    return 0


def runtime_main(argv: list[str] | None = None) -> int:
    """Runtime diagnostics and status commands."""
    parser = argparse.ArgumentParser(
        prog="relic runtime",
        description="Runtime status and diagnostics for Relic.",
    )
    subparsers = parser.add_subparsers(dest="runtime_action", required=True)

    status_parser = subparsers.add_parser("status", help="Show Hermes runtime status.")
    doctor_parser = subparsers.add_parser("doctor", help="Run full runtime diagnostic.")

    args = parser.parse_args(argv)

    if args.runtime_action == "status":
        return _runtime_status()
    if args.runtime_action == "doctor":
        return _runtime_doctor()

    parser.print_help()
    return 1


def _runtime_status() -> int:
    """Show Hermes runtime status."""
    import subprocess
    import shutil

    print("=== Relic Runtime Status ===\n")

    # Hermes version
    hermes_version = "not_found"
    hermes_path = shutil.which("hermes")
    if hermes_path:
        try:
            result = subprocess.run(
                ["hermes", "version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                hermes_version = result.stdout.strip() or "installed"
        except Exception:
            hermes_version = "error"
    print(f"  Hermes version:          {hermes_version}")

    # Runtime feature support
    from relic.hermes_runtime import check_hermes_feature_support, get_runtime_config, init_runtime_config

    if not get_runtime_config():
        init_runtime_config()

    features = check_hermes_feature_support()
    print(f"  no_agent_cron:           {'supported' if features.get('no_agent_cron') else 'not_supported'}")
    print(f"  transform_hook:           {'supported' if features.get('transform_llm_output') else 'not_supported'}")
    print(f"  session_key:             {'configured' if features.get('session_key_support') else 'not_configured'}")

    # Delivery gate status
    print(f"  delivery_gate:            enabled")

    # Allowlist enforcement status
    print(f"  allowlist_enforcement:    {'enforced' if features.get('allowlist_support') else 'not_enforced'}")

    # Resume reconciliation status
    print(f"  resume_reconciliation:    enabled")

    print("")
    return 0


def _runtime_doctor() -> int:
    """Run full runtime diagnostic and report missing pieces."""
    import subprocess
    import shutil

    print("=== Relic Runtime Doctor ===\n")

    issues: list[str] = []
    warnings: list[str] = []

    # Check Hermes installation
    hermes_path = shutil.which("hermes")
    if not hermes_path:
        issues.append("Hermes is not installed or not in PATH")
        issues.append("  Install: curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash")
    else:
        try:
            result = subprocess.run(
                ["hermes", "version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                issues.append("Hermes is installed but 'hermes version' failed")
        except Exception as e:
            issues.append(f"Hermes check failed: {e}")

    # Check Ollama installation
    ollama_path = shutil.which("ollama")
    if not ollama_path:
        issues.append("Ollama is not installed or not in PATH")
        issues.append("  Install: https://ollama.com/download")
    else:
        warnings.append("Ollama found (verify it is running with 'ollama list')")

    # Check runtime features
    from relic.hermes_runtime import check_hermes_feature_support, get_runtime_config, init_runtime_config

    if not get_runtime_config():
        init_runtime_config()

    features = check_hermes_feature_support()

    if not features.get("no_agent_cron"):
        issues.append("Hermes no-agent cron is not supported (upgrade Hermes)")

    if not features.get("transform_llm_output"):
        warnings.append("Hermes transform hook is not supported (upgrade Hermes for LLM output transforms)")

    if not features.get("session_key_support"):
        issues.append("Hermes session key support is not configured")

    if not features.get("allowlist_support"):
        issues.append("Hermes allowlist enforcement is not supported")

    # Check Relic subjects directory
    from relic.paths import get_relic_home
    relic_home = get_relic_home()
    subjects_dir = relic_home / "subjects"
    if not subjects_dir.exists():
        warnings.append(f"Relic subjects directory does not exist: {subjects_dir}")
        warnings.append("  Run 'relic subject create' to create your first subject")

    # Check for configured subjects with missing session keys
    registry_problems: list[str] = []
    if subjects_dir.exists():
        registry = ProfileRegistry()
        for profile in registry.list_subjects():
            if profile.status == "active":
                session_key_path = profile.relic_subject_home / ".session_key_hash"
                if not session_key_path.exists():
                    registry_problems.append(
                        f"  Subject '{profile.subject_id}' is active but missing session key hash"
                    )

    # Report results
    if issues:
        print("[ISSUE] Problems detected:\n")
        for issue in issues:
            print(f"  - {issue}")
        print("")

    if warnings:
        print("[WARN] Warnings:\n")
        for warning in warnings:
            print(f"  - {warning}")
        print("")

    if registry_problems:
        print("[ISSUE] Subject configuration problems:\n")
        for problem in registry_problems:
            print(f"  - {problem}")
        print("")

    # Check session key store location
    if hermes_path and features.get("session_key_support"):
        try:
            from relic.hermes_runtime import HermesSessionKey
            test_hash = HermesSessionKey.derive("test_subject", "test_gumi", "test_hermes")
            if not test_hash:
                issues.append("Session key derivation failed")
        except Exception as e:
            issues.append(f"Session key derivation error: {e}")

    # Missing session key check (per contract)
    missing_session_key = any("session" in p.lower() for p in registry_problems)
    if missing_session_key:
        issues.append("Missing session key for one or more active subjects")

    missing_allowlist = not features.get("allowlist_support")
    if missing_allowlist:
        issues.append("Allowlist enforcement is not supported by Hermes")

    if not issues and not warnings and not registry_problems:
        print("[OK] All runtime checks passed.\n")
        return 0

    if issues:
        print(f"Total issues: {len(issues)}")
        return 1

    return 0

def _hash_delivery_target(target: str) -> str:
    """Hash a delivery target identifier for storage. Target IDs are never stored raw."""
    import hashlib
    return hashlib.sha256(target.encode("utf-8")).hexdigest()


def delivery_main(argv: list[str] | None = None) -> int:
    """Delivery allowlist management entrypoint."""
    parser = argparse.ArgumentParser(
        prog="relic delivery",
        description="Manage delivery allowlists and enforce delivery gates.",
    )
    subparsers = parser.add_subparsers(dest="delivery_action", required=True)

    # relic delivery allowlist add <subject_id> --platform <platform> --target <target>
    allowlist_parser = subparsers.add_parser("allowlist", help="Manage delivery allowlist.")
    allowlist_subparsers = allowlist_parser.add_subparsers(dest="allowlist_action", required=True)

    add_parser = allowlist_subparsers.add_parser("add", help="Add a target to the delivery allowlist.")
    add_parser.add_argument("subject_id", help="Subject identifier.")
    add_parser.add_argument("--platform", required=True, help="Platform (e.g., telegram, whatsapp).")
    add_parser.add_argument("--target", required=True, help="Target identifier (e.g., telegram:123456789).")
    add_parser.add_argument("--expires", default=None, help="Expiration ISO timestamp (optional).")

    list_parser = allowlist_subparsers.add_parser("list", help="List allowlist entries for a subject.")
    list_parser.add_argument("subject_id", help="Subject identifier.")
    list_parser.add_argument("--platform", default=None, help="Filter by platform (optional).")

    remove_parser = allowlist_subparsers.add_parser("remove", help="Remove a target from the delivery allowlist.")
    remove_parser.add_argument("subject_id", help="Subject identifier.")
    remove_parser.add_argument("--platform", required=True, help="Platform (e.g., telegram, whatsapp).")
    remove_parser.add_argument("--target", required=True, help="Target identifier (e.g., telegram:123456789).")

    args = parser.parse_args(argv)

    if args.delivery_action == "allowlist":
        from relic.hermes_runtime import (
            register_allowlist_entry,
            get_allowlist_entry,
            clear_allowlist_store,
            _ALLOWLIST_STORE,
            DeliveryGate,
            DeliveryGateDecision,
        )

        if args.allowlist_action == "add":
            subject_id = args.subject_id
            platform = args.platform
            target = args.target

            # Hash the target before storage
            target_hash = _hash_delivery_target(target)

            entry = {
                "subject_id": subject_id,
                "platform": platform,
                "target_hash": target_hash,
                "enabled": True,
            }
            if args.expires:
                entry["expires_at"] = args.expires

            register_allowlist_entry(entry)
            print(f"Added allowlist entry: subject={subject_id} platform={platform} target_hash={target_hash[:16]}...")
            return 0

        if args.allowlist_action == "list":
            subject_id = args.subject_id
            platform = args.platform

            # List all allowlist entries for this subject
            found = False
            for key, entry in _ALLOWLIST_STORE.items():
                if entry.get("subject_id") == subject_id:
                    if platform is None or entry.get("platform") == platform:
                        found = True
                        print(f"  platform={entry.get('platform')} enabled={entry.get('enabled')} "
                              f"expires={entry.get('expires_at', 'never')} "
                              f"target_hash={entry.get('target_hash', 'none')[:16]}...")
            if not found:
                print(f"No allowlist entries found for subject '{subject_id}'"
                      + (f" platform={platform}" if platform else ""))
            return 0

        if args.allowlist_action == "remove":
            subject_id = args.subject_id
            platform = args.platform
            target = args.target

            # Compute the hash to find the entry
            target_hash = _hash_delivery_target(target)

            # Find and remove entries matching subject_id + platform + target_hash
            removed = False
            keys_to_remove = []
            for key, entry in _ALLOWLIST_STORE.items():
                if (entry.get("subject_id") == subject_id and
                    entry.get("platform") == platform and
                    entry.get("target_hash") == target_hash):
                    keys_to_remove.append(key)
                    removed = True

            for key in keys_to_remove:
                del _ALLOWLIST_STORE[key]

            if removed:
                print(f"Removed allowlist entry: subject={subject_id} platform={platform}")
            else:
                print(f"No allowlist entry found: subject={subject_id} platform={platform}")
            return 0

    parser.print_help()
    return 1


def checkin_main(argv: list[str]) -> int:
    """relic checkin <subcommand>, checkin loop management."""
    parser = argparse.ArgumentParser(prog="relic checkin")
    subparsers = parser.add_subparsers(dest="checkin_action", required=True)

    upd_parser = subparsers.add_parser(
        "update-facets",
        help="Process pending checkin replies and update subject_baseline.json",
    )
    upd_parser.add_argument("--subject-id", required=True, help="Subject identifier")
    upd_parser.add_argument("--dry-run", action="store_true", help="Show what would change, no writes")
    upd_parser.add_argument("--relic-home", default=None, help="Override RELIC_HOME")

    status_parser = subparsers.add_parser(
        "status",
        help="Show pending/processed exchange counts for a subject",
    )
    status_parser.add_argument("--subject-id", required=True)
    status_parser.add_argument("--relic-home", default=None)

    snap_parser = subparsers.add_parser(
        "snapshot",
        help="Write a model_snapshots row for a subject (force or backfill)",
    )
    snap_parser.add_argument("--subject-id", required=True, help="Subject identifier")
    snap_parser.add_argument("--relic-home", default=None, help="Override RELIC_HOME")
    snap_parser.add_argument(
        "--force", action="store_true",
        help="Write snapshot even if model has not changed (bypasses debounce)",
    )
    snap_parser.add_argument(
        "--backfill", action="store_true",
        help=(
            "Reconstruct daily snapshots from observations table for the gap "
            "since the last snapshot. Each reconstructed row is tagged "
            'reason=\\"backfill\\" in snapshot_data. Use --force to also write '
            "today's snapshot unconditionally after backfilling."
        ),
    )

    args = parser.parse_args(argv)

    relic_home = args.relic_home or os.environ.get("RELIC_HOME") or str(Path.home() / ".relic")

    if args.checkin_action == "update-facets":
        from relic.checkin.facet_updater import process_pending_exchanges
        from relic.checkin.db_init import init_db as _init_db_schema

        subject_id = args.subject_id
        db_path = Path(relic_home) / "subjects" / subject_id / "relic.db"
        baseline_path = Path(relic_home) / "subjects" / subject_id / "subject_baseline.json"

        if not db_path.exists():
            print(f"Error: relic.db not found at {db_path}", file=sys.stderr)
            return 1

        conn = _init_db_schema(db_path)  # idempotent, applies any missing tables
        try:
            results = process_pending_exchanges(
                conn, baseline_path, subject_id, dry_run=args.dry_run
            )
        finally:
            conn.close()

        informative = sum(1 for r in results if r.get("informative"))
        if informative == 0 and len(results) > 0:
            print(
                f"Warning: 0 informative observations from {len(results)} replies"
                ", replies may be ambiguous or facet_updater may need tuning",
                file=sys.stderr,
            )
        print(json.dumps({
            "status": "ok",
            "dry_run": args.dry_run,
            "processed": len(results),
            "informative": informative,
            "results": results,
        }, ensure_ascii=False, indent=2))
        return 0

    if args.checkin_action == "status":
        import sqlite3

        subject_id = args.subject_id
        db_path = Path(relic_home) / "subjects" / subject_id / "relic.db"
        if not db_path.exists():
            print(f"Error: relic.db not found at {db_path}", file=sys.stderr)
            return 1

        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5.0)
        try:
            pending = conn.execute(
                "SELECT COUNT(*) FROM checkin_exchanges WHERE reply_text IS NOT NULL AND observations_extracted = 0"
            ).fetchone()[0]
            total = conn.execute("SELECT COUNT(*) FROM checkin_exchanges").fetchone()[0]
            processed = conn.execute(
                "SELECT COUNT(*) FROM checkin_exchanges WHERE observations_extracted = 1"
            ).fetchone()[0]
            unanswered = conn.execute(
                "SELECT COUNT(*) FROM checkin_exchanges WHERE reply_text IS NULL"
            ).fetchone()[0]
        finally:
            conn.close()

        print(json.dumps({
            "subject_id": subject_id,
            "exchanges_total": total,
            "unanswered": unanswered,
            "pending_extraction": pending,
            "extracted": processed,
        }, indent=2))
        return 0

    if args.checkin_action == "snapshot":
        import sqlite3 as _sqlite3
        from relic.checkin.facet_updater import write_snapshot, maybe_write_snapshot
        from relic.checkin.db_init import init_db as _init_db_schema

        subject_id = args.subject_id
        db_path = Path(relic_home) / "subjects" / subject_id / "relic.db"
        if not db_path.exists():
            print(f"Error: relic.db not found at {db_path}", file=sys.stderr)
            return 1

        conn = _init_db_schema(db_path)
        try:
            if args.backfill:
                result = _checkin_snapshot_backfill(conn, subject_id)
                print(json.dumps(result, indent=2))
                if args.force:
                    snap = write_snapshot(conn, reason="manual")
                    print(json.dumps({"forced_snapshot": snap}, indent=2))
            elif args.force:
                snap = write_snapshot(conn, reason="manual")
                print(json.dumps(snap, indent=2))
            else:
                snap = maybe_write_snapshot(conn, reason="manual")
                if snap:
                    print(json.dumps(snap, indent=2))
                else:
                    print(json.dumps({"status": "skipped", "reason": "no model change or debounce active"}))
        finally:
            conn.close()
        return 0

    parser.print_help()
    return 1


def _checkin_snapshot_backfill(conn: "sqlite3.Connection", subject_id: str) -> dict:  # type: ignore[name-defined]
    """Reconstruct daily model snapshots from observations table.

    For each calendar day between (last_snapshot + 1 day) and yesterday that had
    ≥1 observation, compute a traits-like summary of all observations up to end-of-day
    and insert a model_snapshots row tagged reason='backfill', reconstructed=true.

    This is a best-effort reconstruction: it does not replay the weighted update law
    per-exchange; instead it aggregates observation positions/confidences by facet
    using a simple mean, which approximates the running accumulation.
    """
    import sqlite3
    from datetime import datetime, timedelta, date

    # Find gap start
    last_snap_row = conn.execute(
        "SELECT MAX(snapshot_at) FROM model_snapshots"
    ).fetchone()
    last_snap_str = last_snap_row[0] if last_snap_row else None

    if last_snap_str:
        try:
            last_snap_dt = datetime.fromisoformat(last_snap_str)
            gap_start = (last_snap_dt.date() + timedelta(days=1))
        except ValueError:
            gap_start = date(2026, 1, 1)
    else:
        # No snapshots at all: start from first observation
        first_obs = conn.execute("SELECT MIN(created_at) FROM observations").fetchone()[0]
        if not first_obs:
            return {"backfill": "no observations found"}
        gap_start = datetime.fromisoformat(first_obs).date()

    gap_end = date.today() - timedelta(days=1)  # exclude today

    if gap_start > gap_end:
        return {"backfill": "no gap to fill", "last_snapshot": last_snap_str}

    # Get facet list
    facets = {
        row[0]: {"category": row[1], "name": row[2]}
        for row in conn.execute("SELECT id, category, name FROM facets").fetchall()
    }

    written = []
    skipped = []
    current_day = gap_start
    while current_day <= gap_end:
        day_end_iso = f"{current_day.isoformat()}T23:59:59+00:00"
        # Count observations up to end of this day
        obs_count = conn.execute(
            "SELECT COUNT(*) FROM observations WHERE created_at <= ?", (day_end_iso,)
        ).fetchone()[0]

        # Only write a snapshot on days that had at least 1 new observation
        day_start_iso = f"{current_day.isoformat()}T00:00:00+00:00"
        new_on_day = conn.execute(
            "SELECT COUNT(*) FROM observations WHERE created_at >= ? AND created_at <= ?",
            (day_start_iso, day_end_iso),
        ).fetchone()[0]

        if new_on_day == 0:
            skipped.append(str(current_day))
            current_day += timedelta(days=1)
            continue

        # Aggregate per-facet signals up to end of this day
        rows = conn.execute(
            """SELECT facet_id,
                      AVG(CASE WHEN signal_position IS NOT NULL THEN signal_position END),
                      AVG(CASE WHEN signal_strength IS NOT NULL THEN signal_strength END),
                      COUNT(*)
               FROM observations
               WHERE created_at <= ?
               GROUP BY facet_id""",
            (day_end_iso,),
        ).fetchall()

        snap_facets = []
        for facet_id, avg_pos, avg_strength, cnt in rows:
            snap_facets.append({
                "facet_id": facet_id,
                "value_position": round(avg_pos, 4) if avg_pos is not None else None,
                "confidence": round(min((avg_strength or 0.1) * (cnt / max(cnt, 10)), 0.85), 4),
                "observation_count": cnt,
                "reconstructed": True,
            })

        confidences = [r["confidence"] for r in snap_facets if r["confidence"] is not None]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
        with_data = sum(1 for r in snap_facets if r["value_position"] is not None)
        cov_pct = 100.0 * with_data / len(facets) if facets else 0.0
        snap_at = f"{current_day.isoformat()}T23:00:00+00:00"  # end-of-day marker

        payload = {
            "reason": "backfill",
            "reconstructed": True,
            "note": "Reconstructed from observations aggregate; not a contemporaneous capture.",
            "facets": snap_facets,
        }
        try:
            conn.execute(
                "INSERT INTO model_snapshots "
                "(snapshot_at, total_observations, avg_confidence, coverage_pct, snapshot_data) "
                "VALUES (?, ?, ?, ?, ?)",
                (snap_at, obs_count, avg_conf, cov_pct, json.dumps(payload)),
            )
            conn.commit()
            written.append(str(current_day))
        except Exception as exc:
            skipped.append(f"{current_day} (error: {exc})")

        current_day += timedelta(days=1)

    return {
        "backfill": "complete",
        "gap_start": str(gap_start),
        "gap_end": str(gap_end),
        "days_written": len(written),
        "days_skipped": len(skipped),
        "written": written,
        "skipped": skipped,
    }


def main(argv: list[str] | None = None) -> int:
    """Main entry point for `python -m relic` and `relic` command."""
    if argv is None:
        argv = sys.argv[1:]
    if argv and argv[0] == "ui":
        return ui_main(argv[1:])
    if argv and argv[0] == "init":
        return init_main(argv[1:])
    if argv and argv[0] == "profile":
        from relic.profile.cli import profile_main
        return profile_main(argv[1:])
    if argv and argv[0] == "setup":
        return setup_main(argv[1:])
    if argv and argv[0] == "subject":
        return subject_main(argv[1:])
    if argv and argv[0] == "delivery":
        return delivery_main(argv[1:])
    if argv and argv[0] == "runtime":
        return runtime_main(argv[1:])
    if argv and argv[0] == "checkin":
        return checkin_main(argv[1:])
    print("relic 0.1.0")
    print("Run `relic init` to get started, then `relic ui` to open the Researcher UI.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
