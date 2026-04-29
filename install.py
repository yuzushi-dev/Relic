#!/usr/bin/env python3
"""
Relic installation wizard - Arasaka-style TUI.

Guides you through connecting Relic to your Hermes instance:
subject configuration, runtime directory, hook compilation and registration,
check-in schedule, past-message backfill, and cron setup.

Tested on Hermes Agent 0.11.0.

Usage:
    python install.py
    python install.py --dry-run       # preview without writing anything
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
TESTED_HERMES = "0.11.0"
TOTAL_STEPS = 9

# ── ANSI palette ───────────────────────────────────────────────────────────────

def _c(r: int, g: int, b: int) -> str:
    return f"\033[38;2;{r};{g};{b}m"

RST   = "\033[0m"
BOLD  = "\033[1m"
RED   = _c(215, 38, 56)
REDS  = _c(255, 90, 107)
GOLD  = _c(198, 166, 103)
GOLDD = _c(110, 90, 50)
WHT   = _c(243, 236, 232)
MUT   = _c(143, 129, 129)
GRN   = _c(132, 209, 164)
WARN  = _c(220, 160, 60)

def r(s: str)  -> str: return f"{RED}{s}{RST}"
def rs(s: str) -> str: return f"{REDS}{s}{RST}"
def g(s: str)  -> str: return f"{GOLD}{s}{RST}"
def w(s: str)  -> str: return f"{WHT}{s}{RST}"
def m(s: str)  -> str: return f"{MUT}{s}{RST}"
def gr(s: str) -> str: return f"{GRN}{s}{RST}"
def wa(s: str) -> str: return f"{WARN}{s}{RST}"
def b(s: str)  -> str: return f"{BOLD}{s}{RST}"

# ── Terminal helpers ───────────────────────────────────────────────────────────

def tw() -> int:
    return min(shutil.get_terminal_size((80, 24)).columns, 100)

def clear() -> None:
    print("\033[2J\033[H", end="", flush=True)

def nl(n: int = 1) -> None:
    print("\n" * (n - 1))

def hr(char: str = "─") -> None:
    print(f"{GOLDD}{char * tw()}{RST}")

def _strip(s: str) -> str:
    return re.sub(r"\033\[[^m]*m", "", s)

def center(text: str) -> None:
    pad = max(0, (tw() - len(_strip(text))) // 2)
    print(" " * pad + text)

def indent(text: str, n: int = 4) -> None:
    print(" " * n + text)

# ── Header ─────────────────────────────────────────────────────────────────────

_LOGO = [
    r" ____  _____ _     ___ ____ ",
    r"|  _ \| ____| |   |_ _/ ___|",
    r"| |_) |  _| | |    | | |    ",
    r"|  _ < | |___| |___ | | |___",
    r"|_| \_\_____|_____|___\____|",
]

def header(step: int = 0, total: int = 0) -> None:
    clear()
    w = tw()
    nl()
    print(f"  {GOLD}╔{'═' * (w - 4)}╗{RST}")
    print(f"  {GOLD}║{RST}{' ' * (w - 4)}{GOLD}║{RST}")
    if w >= 68:
        for line in _LOGO:
            pad = max(0, (w - 4 - len(line)) // 2)
            tail = max(0, w - 4 - pad - len(line))
            print(f"  {GOLD}║{RST}{' ' * pad}{RED}{BOLD}{line}{RST}{' ' * tail}{GOLD}║{RST}")
    else:
        logo = "RELIC"
        pad = (w - 4 - len(logo)) // 2
        print(f"  {GOLD}║{RST}{' ' * pad}{RED}{BOLD}{logo}{RST}{' ' * (w - 4 - pad - len(logo))}{GOLD}║{RST}")
    print(f"  {GOLD}║{RST}{' ' * (w - 4)}{GOLD}║{RST}")
    tag = "荒坂 CORP  ·  ENGRAMMATIC TRANSFER SYSTEM  ·  SECURE YOUR SOUL"
    pad = max(0, (w - 4 - len(tag)) // 2)
    tail = max(0, w - 4 - pad - len(tag))
    print(f"  {GOLD}║{RST}{' ' * pad}{GOLD}{tag}{RST}{' ' * tail}{GOLD}║{RST}")
    print(f"  {GOLD}║{RST}{' ' * (w - 4)}{GOLD}║{RST}")
    print(f"  {GOLD}╚{'═' * (w - 4)}╝{RST}")
    nl()
    if step and total:
        filled = f"{GOLD}{'·' * step}{RST}"
        empty  = f"{GOLDD}{'·' * (total - step)}{RST}"
        indent(f"{MUT}Step {step} of {total}{RST}  {filled}{empty}")
        nl()

# ── Input helpers ──────────────────────────────────────────────────────────────

def ask(prompt: str, default: str = "", secret: bool = False) -> str:
    dflt = f"  {MUT}[{default}]{RST}" if default else ""
    display = f"  {GOLD}▶{RST}  {WHT}{prompt}{RST}{dflt}  "
    if secret:
        import getpass
        val = getpass.getpass(display) or default
    else:
        try:
            val = input(display).strip() or default
        except (EOFError, KeyboardInterrupt):
            nl(); abort()
    return val

def ask_int(prompt: str, default: int, lo: int, hi: int) -> int:
    while True:
        raw = ask(prompt, default=str(default))
        try:
            val = int(raw)
            if lo <= val <= hi:
                return val
            indent(f"  {WARN}Enter a value between {lo} and {hi}.{RST}")
        except ValueError:
            indent(f"  {WARN}Enter a number.{RST}")

def confirm(prompt: str, default: bool = True) -> bool:
    opts = f"{GOLD}Y{RST}/{MUT}n{RST}" if default else f"{MUT}y{RST}/{GOLD}N{RST}"
    display = f"  {GOLD}▶{RST}  {WHT}{prompt}{RST}  [{opts}]  "
    try:
        raw = input(display).strip().lower()
    except (EOFError, KeyboardInterrupt):
        nl(); abort()
    return (raw in ("y", "yes")) if raw else default

def abort() -> None:
    nl()
    center(f"{RED}Installation aborted.{RST}")
    nl()
    center(m("Your soul remains uncharted."))
    nl()
    sys.exit(1)

# ── State ──────────────────────────────────────────────────────────────────────

@dataclass
class State:
    # subject
    subject_name: str = ""
    subject_id: str = ""
    subject_telegram_id: str = ""
    # paths
    data_dir: str = ""
    hermes_bin: str = "hermes"
    hermes_home: str = ""
    hooks_dir: str = ""
    # check-in schedule
    checkin_hour_start: int = 9
    checkin_hour_end: int = 22
    checkin_interval_min: int = 30
    # integrations
    relational_agent: str = ""
    relational_agent_ids: str = ""
    enable_telegram: bool = False
    enable_biofeedback: bool = False
    # paperclip
    enable_paperclip: bool = False
    paperclip_url: str = "http://localhost:3100"
    paperclip_company_id: str = ""
    paperclip_bio_analyst_key: str = ""
    paperclip_bio_reviewer_id: str = ""
    paperclip_inq_analyst_key: str = ""
    paperclip_inq_reviewer_id: str = ""
    paperclip_health_analyst_key: str = ""
    paperclip_health_reviewer_id: str = ""
    paperclip_humanness_analyst_key: str = ""
    paperclip_humanness_reviewer_id: str = ""
    # backfill
    run_backfill: bool = False
    backfill_path: str = ""
    backfill_count: int = 0
    # runtime
    dry_run: bool = False
    hermes_ok: bool = False
    hermes_version: str = ""
    failed_steps: list[str] = field(default_factory=list)
    manual_steps: list[str] = field(default_factory=list)

    @property
    def checkin_schedule(self) -> str:
        return (
            f"*/{self.checkin_interval_min} "
            f"{self.checkin_hour_start}-{self.checkin_hour_end} * * *"
        )

# ── Steps ──────────────────────────────────────────────────────────────────────

def step_welcome(state: State) -> None:
    header()
    indent(b("Installation Wizard"))
    nl()
    indent(w("This wizard will guide you through configuring Relic"))
    indent(w("for your personal Hermes instance."))
    nl()
    hr("·")
    nl()
    indent(f"{GOLD}What will be set up:{RST}")
    nl()
    for item in [
        "Subject identity and runtime data directory",
        "Hermes hooks: relic-capture · relic-bootstrap",
        "Check-in schedule (active hours and probe frequency)",
        "Past-message backfill - import existing signal into inbox",
        "Cron jobs: 6 core + 10 daily/weekly + 13 monthly specialist analyzers",
        "Environment file (.env) with your full configuration",
    ]:
        indent(f"  {GOLDD}◈{RST}  {WHT}{item}{RST}")
    nl()
    hr("·")
    nl()
    indent(f"{MUT}Tested on Hermes Agent {TESTED_HERMES}.{RST}")
    indent(f"{MUT}Other versions may work but are not verified.{RST}")
    if state.dry_run:
        nl()
        indent(f"{WARN}DRY RUN - no files will be written, no commands executed.{RST}")
    nl()
    input(f"  {GOLD}▶{RST}  {MUT}Press Enter to begin...{RST}  ")


def step_prereqs(state: State) -> None:
    header(1, TOTAL_STEPS)
    indent(b("Prerequisites"))
    nl()

    checks: list[tuple[str, bool, str]] = []

    major, minor = sys.version_info[:2]
    py_ok = (major, minor) >= (3, 12)
    checks.append((f"Python {major}.{minor}", py_ok,
                   "" if py_ok else "Python 3.12+ required"))

    bin_path = shutil.which(state.hermes_bin)
    hermes_found = bin_path is not None
    checks.append((f"hermes binary ({state.hermes_bin})", hermes_found,
                   "" if hermes_found else f"'{state.hermes_bin}' not found in PATH"))

    # check Node/npm for hook compilation
    node_path = shutil.which("node")
    node_ok = node_path is not None
    checks.append(("node  (hook compilation)", node_ok,
                   "" if node_ok else "node not found - hooks will not be compiled"))

    if hermes_found:
        try:
            result = subprocess.run([state.hermes_bin, "--version"],
                                    capture_output=True, text=True, timeout=5)
            raw = (result.stdout + result.stderr).strip()
            m_ver = re.search(r"(\d+\.\d+\.\d+)", raw)
            ver = m_ver.group(1) if m_ver else raw[:20]
            state.hermes_version = ver
            ver_ok = ver == TESTED_HERMES
            state.hermes_ok = True
            checks.append((f"Hermes Agent version {ver}", ver_ok,
                            f"Tested on {TESTED_HERMES}; this version is untested"
                            if not ver_ok else ""))
        except Exception as e:
            checks.append(("Hermes Agent version", False, str(e)))
    else:
        state.hermes_ok = False

    for label, ok, note in checks:
        icon   = gr("✓") if ok else (wa("⚠") if note else r("✗"))
        status = gr("ok") if ok else (wa("warning") if note else r("fail"))
        indent(f"  {icon}  {WHT}{label}{RST}  {MUT}···{RST}  {status}")
        if note:
            indent(f"     {MUT}{note}{RST}")
    nl()

    if not py_ok or not hermes_found:
        hr(); nl()
        indent(r("One or more required components are missing."))
        indent(m("Resolve the issues above and re-run the installer."))
        nl(); sys.exit(1)

    if hermes_found and state.hermes_version != TESTED_HERMES:
        if not confirm("Hermes Agent version is untested. Continue anyway?"):
            abort()


def step_subject(state: State) -> None:
    header(2, TOTAL_STEPS)
    indent(b("Subject Configuration"))
    nl()
    indent(m("The subject is the person whose personality will be modeled."))
    indent(m("In most cases, this is you."))
    nl()
    hr("·")
    nl()

    state.subject_name = ask("Subject display name", default="Demo Subject")
    nl()
    state.subject_id = ask(
        "Subject ID  (slug, no spaces - used in logs and file names)",
        default=state.subject_name.lower().replace(" ", "-"),
    )
    nl()
    indent(m("Telegram ID: the numeric sender ID that arrives in message events."))
    indent(m("The capture hook uses this to filter messages.  Leave blank to set manually later."))
    nl()
    state.subject_telegram_id = ask(
        "Subject Telegram ID  (numeric, optional)",
        default="",
    )


def step_datadir(state: State) -> None:
    header(3, TOTAL_STEPS)
    indent(b("Runtime Data Directory"))
    nl()
    indent(m("Relic stores its SQLite database, inbox, portraits, and logs here."))
    indent(m("This directory will be created if it does not exist."))
    nl()
    hr("·")
    nl()

    default_dir = str(Path.home() / ".relic" / state.subject_id)
    raw = ask("Data directory path", default=default_dir)
    state.data_dir = str(Path(raw).expanduser().resolve())
    nl()
    indent(f"  {MUT}Resolved:{RST}  {WHT}{state.data_dir}{RST}")


def step_hermes(state: State) -> None:
    header(4, TOTAL_STEPS)
    indent(b("Hermes Configuration"))
    nl()
    indent(m("Hooks will be compiled (TypeScript → JS) and registered with your Hermes instance."))
    nl()
    hr("·")
    nl()

    state.hermes_bin = ask("Hermes binary", default=state.hermes_bin) or "hermes"
    nl()
    default_home = os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))
    state.hermes_home = ask("Hermes home directory", default=default_home)
    nl()
    default_hooks = str(Path(state.hermes_home) / "hooks")
    state.hooks_dir = ask(
        "Hermes hooks directory  (hook folders will be linked here)",
        default=default_hooks,
    )
    nl()
    indent(f"{GOLD}Hooks that will be registered:{RST}")
    nl()
    for hook in ["relic-capture", "relic-bootstrap"]:
        src = REPO_ROOT / "hooks" / hook
        exists = src.exists()
        icon = gr("✓") if exists else wa("⚠")
        indent(f"  {icon}  {WHT}{hook}{RST}  {MUT}{src}{RST}")
    nl()
    indent(m("Each hook folder contains a handler.ts that Hermes compiles on registration."))
    indent(m("Your subject ID and data dir will be written to the hook env at install time."))


def step_checkin(state: State) -> None:
    header(5, TOTAL_STEPS)
    indent(b("Check-in Schedule"))
    nl()
    indent(m("Relic sends targeted personality-probe questions via your relational agent."))
    indent(m("Configure when and how often probes are delivered."))
    nl()
    hr("·")
    nl()

    indent(f"{GOLD}Active window{RST}  {MUT}(probes will only fire within these hours){RST}")
    nl()
    state.checkin_hour_start = ask_int(
        "Start hour  (0–23, 24h format)",
        default=9, lo=0, hi=23,
    )
    state.checkin_hour_end = ask_int(
        "End hour  (0–23, must be > start)",
        default=22, lo=state.checkin_hour_start + 1, hi=23,
    )
    nl()

    indent(f"{GOLD}Probe frequency{RST}")
    nl()
    state.checkin_interval_min = ask_int(
        "Interval in minutes between probes  (15–120)",
        default=30, lo=15, hi=120,
    )
    nl()
    hr("·")
    nl()
    indent(f"{GOLD}Resulting cron schedule:{RST}")
    nl()
    indent(f"  {REDS}{state.checkin_schedule}{RST}")
    indent(f"  {MUT}→ every {state.checkin_interval_min} min, "
           f"{state.checkin_hour_start}:00 – {state.checkin_hour_end}:59{RST}")



def _try_paperclip_setup(state: State) -> None:
    """Connect to Paperclip, create company + agents, store keys in state."""
    import urllib.error, urllib.request, shutil, subprocess

    def _papi(method: str, path: str, data: dict | None = None, token: str = "") -> dict:
        import json as _j
        body = _j.dumps(data).encode() if data is not None else None
        hdrs: dict = {"Content-Type": "application/json"}
        if token:
            hdrs["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(
            f"{state.paperclip_url}/api{path}",
            data=body, headers=hdrs, method=method,
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            raw = r.read()
            return _j.loads(raw) if raw else {}

    # Check connectivity
    try:
        health = _papi("GET", "/health")
        indent(gr(f"  Paperclip {health.get('version','?')} — connected"))
    except Exception:
        nl()
        indent(wa("  Paperclip not reachable at " + state.paperclip_url))
        indent(m("  Start it with:  npx paperclipai run"))
        indent(m("  Then run later: python3 scripts/setup_paperclip.py"))
        state.enable_paperclip = False
        return

    # Which pipelines?
    nl()
    indent(m("Which pipelines should Paperclip manage?"))
    indent(m("  [b] Biofeedback Correlation only"))
    indent(m("  [i] Inquiry Verification only"))
    indent(m("  [h] Health Monitor only"))
    indent(m("  [a] All three  (default)"))
    nl()
    pipelines = ask("Pipelines", default="a").strip().lower()
    if pipelines not in ("a", "b", "i", "h"):
        pipelines = "a"

    # Company name
    company_name = ask("Company name", default="Relic")

    # Create company
    try:
        company = _papi("POST", "/companies", {
            "name": company_name,
            "goal": (
                "Scientific analysis of biofeedback/personality correlations "
                "and adversarial verification of behavioral findings."
            ),
        })
        state.paperclip_company_id = company["id"]
        indent(gr(f"  Company '{company_name}' created"))
    except Exception as exc:
        indent(wa(f"  Failed to create company: {exc}"))
        return

    cid = state.paperclip_company_id
    npx = shutil.which("npx") or "npx"

    def _make_agent(spec: dict, hb: dict) -> str:
        a = _papi("POST", f"/companies/{cid}/agents", spec)
        _papi("PATCH", f"/agents/{a['id']}", {"runtimeConfig": {"heartbeat": hb}})
        return a["id"], a.get("urlKey", "")

    def _gemini_agent_config(timeout_sec: int = 300) -> dict:
        return {
            "model": "gemini-2.5-flash",
            "timeoutSec": timeout_sec,
            "command": os.environ.get(
                "PAPERCLIP_GEMINI_FALLBACK_COMMAND",
                "/home/cristina/.paperclip/bin/paperclip-gemini-fallback",
            ),
            "env": {
                "PAPERCLIP_HERMES_FALLBACKS": os.environ.get(
                    "PAPERCLIP_HERMES_FALLBACKS",
                    "ollama-cloud:gpt-oss:20b,openrouter:openrouter/free",
                ),
                "PAPERCLIP_HERMES_FALLBACK_TIMEOUT_SEC": "60",
                "PAPERCLIP_HERMES_FALLBACK_MAX_TURNS": "12",
            },
        }

    def _make_key(url_key: str, key_name: str) -> str:
        out = subprocess.run(
            [npx, "paperclipai", "agent", "local-cli", url_key,
             "-C", cid, "--key-name", key_name,
             "--no-install-skills", "--api-base", state.paperclip_url, "--json"],
            capture_output=True, text=True,
        )
        if out.returncode == 0:
            import json as _j
            return _j.loads(out.stdout)["key"]["token"]
        return ""

    if pipelines in ("a", "b"):
        aid, ukey = _make_agent(
            {"name": "Biofeedback Analyst",
             "capabilities": "Nightly Spearman correlation: physiological signals × personality facets.",
             "adapterType": "process",
             "adapterConfig": {"command": "python3", "args": ["-m", "relic.biofeedback_correlation"],
                               "env": {"PYTHONPATH": "src"}, "timeoutSec": 600}},
            {"enabled": True, "intervalSec": 86400, "maxConcurrentRuns": 1},
        )
        state.paperclip_bio_analyst_key = _make_key(ukey, "relic-bio-analyst")
        rid, _ = _make_agent(
            {"name": "Biofeedback Reviewer",
             "capabilities": "Reviews biofeedback correlation results and flags findings.",
             "adapterType": "gemini_local",
             "adapterConfig": _gemini_agent_config(300)},
            {"enabled": True, "intervalSec": 600, "maxConcurrentRuns": 1},
        )
        state.paperclip_bio_reviewer_id = rid
        indent(gr("  Biofeedback agents created"))

    if pipelines in ("a", "i"):
        aid, ukey = _make_agent(
            {"name": "Inquiry Analyst",
             "capabilities": "Adversarial hypothesis verification on behavioral observations.",
             "adapterType": "process",
             "adapterConfig": {"command": "python3", "args": ["-m", "relic.relic_inquiry_team"],
                               "env": {"PYTHONPATH": "src", "RELIC_INQUIRY_TEAM": "true"},
                               "timeoutSec": 600}},
            {"enabled": True, "intervalSec": 86400, "maxConcurrentRuns": 1},
        )
        state.paperclip_inq_analyst_key = _make_key(ukey, "relic-inq-analyst")
        rid, _ = _make_agent(
            {"name": "Inquiry Reviewer",
             "capabilities": "Reviews personality and behavioral findings, proposes verdicts.",
             "adapterType": "gemini_local",
             "adapterConfig": _gemini_agent_config(300)},
            {"enabled": True, "intervalSec": 600, "maxConcurrentRuns": 1},
        )
        state.paperclip_inq_reviewer_id = rid
        indent(gr("  Inquiry agents created"))

    if pipelines in ("a", "h"):
        aid, ukey = _make_agent(
            {"name": "Health Analyst",
             "capabilities": "Every 12h: computes model health (confidence/coverage/loop-risk) and submits structured health issues.",
             "adapterType": "process",
             "adapterConfig": {"command": "python3", "args": ["-m", "relic.health_monitor"],
                               "env": {"PYTHONPATH": "src"}, "timeoutSec": 120}},
            {"enabled": True, "intervalSec": 43200, "maxConcurrentRuns": 1},
        )
        state.paperclip_health_analyst_key = _make_key(ukey, "relic-health-analyst")
        rid, _ = _make_agent(
            {"name": "Health Strategist",
             "capabilities": "Reviews health reports, evaluates confidence/coverage trends and loop risk, proposes interventions.",
             "adapterType": "gemini_local",
             "adapterConfig": _gemini_agent_config(300)},
            {"enabled": True, "intervalSec": 600, "maxConcurrentRuns": 1},
        )
        state.paperclip_health_reviewer_id = rid
        indent(gr("  Health agents created"))


def step_integrations(state: State) -> None:
    header(6, TOTAL_STEPS)
    indent(b("Optional Integrations"))
    nl()
    indent(m("All integrations are optional. You can enable them later via .env."))
    nl()
    hr("·")
    nl()

    indent(f"{GOLD}Passive observation  (relational agent){RST}")
    nl()
    indent(m("If you have a relational agent in OpenClaw, Relic can passively scan"))
    indent(m("its session transcripts for behavioral meta-signals every 6 hours."))
    nl()
    state.relational_agent = ask(
        "Relational agent name  (e.g. 'companion', leave blank to skip)",
        default="",
    )
    if state.relational_agent:
        state.relational_agent_ids = ask(
            "Additional agent IDs to scan  (comma-separated, optional)",
            default="",
        )
    nl()
    hr("·")
    nl()

    indent(f"{GOLD}Telegram delivery{RST}")
    nl()
    indent(m("Enables live check-in delivery via Telegram."))
    indent(m("Requires a Telegram channel configured in your OpenClaw instance."))
    nl()
    state.enable_telegram = confirm("Enable Telegram check-ins?", default=False)
    nl()
    hr("·")
    nl()

    indent(f"{GOLD}Biofeedback  (Zepp / Amazfit){RST}")
    nl()
    indent(m("Ingests HRV and sleep data as physiological signal."))
    nl()
    state.enable_biofeedback = confirm("Enable biofeedback integration?", default=False)

    nl()
    hr("·")
    nl()

    indent(f"{GOLD}Paperclip  (AI orchestration for analysis review){RST}")
    nl()
    indent(m("Creates a Paperclip company with Gemini review agents for the pipelines"))
    indent(m("you enable. Requires Paperclip installed and running:"))
    indent(m("  npm install -g paperclipai  →  npx paperclipai run"))
    nl()
    state.enable_paperclip = confirm("Enable Paperclip integration?", default=False)
    if state.enable_paperclip:
        state.paperclip_url = ask(
            "Paperclip API URL",
            default="http://localhost:3100",
        )
        nl()
        _try_paperclip_setup(state)


def step_backfill(state: State) -> None:
    header(7, TOTAL_STEPS)
    indent(b("Past-Message Backfill"))
    nl()
    indent(m("If you have existing messages you want to feed into the model,"))
    indent(m("import them now. The extraction pipeline will process them on first run."))
    nl()
    hr("·")
    nl()

    indent(f"{GOLD}Expected format{RST}  {MUT}(newline-delimited JSON, one message per line):{RST}")
    nl()
    example = (
        '{"message_id":"msg-001","from":"telegram:'
        + (state.subject_id or "<subject_id>")
        + '","content":"...","channel_id":"telegram","received_at":"2026-01-01T10:00:00Z"}'
    )
    indent(f"  {MUT}{example}{RST}")
    nl()
    indent(m(f"  The 'from' field must match  telegram:{state.subject_id or '<subject_id>'}"))
    nl()
    hr("·")
    nl()

    state.run_backfill = confirm(
        "Do you have past messages to import?",
        default=False,
    )
    if not state.run_backfill:
        return

    nl()
    while True:
        raw = ask("Path to JSONL file", default="")
        if not raw:
            if not confirm("Skip backfill?", default=True):
                continue
            state.run_backfill = False
            return

        p = Path(raw).expanduser().resolve()
        if not p.exists():
            indent(f"  {WARN}File not found: {p}{RST}")
            continue
        if not p.suffix == ".jsonl" and not p.suffix == ".json":
            if not confirm(f"File extension is '{p.suffix}' - use it anyway?", default=True):
                continue

        # count and preview
        try:
            lines = [l for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
            count = len(lines)
            if count == 0:
                indent(f"  {WARN}File is empty.{RST}")
                continue
            # validate first line is valid JSON with expected keys
            first = json.loads(lines[0])
            missing = [k for k in ("message_id", "content", "received_at") if k not in first]
            if missing:
                indent(f"  {WARN}First record missing keys: {', '.join(missing)}{RST}")
                if not confirm("Use file anyway?", default=False):
                    continue

            state.backfill_path = str(p)
            state.backfill_count = count
            nl()
            indent(f"  {GRN}✓{RST}  {WHT}{count} messages found{RST}")
            indent(f"     {MUT}First message: {first.get('message_id', '-')}  ·  "
                   f"{first.get('received_at', '-')[:10]}{RST}")
            break
        except (json.JSONDecodeError, Exception) as exc:
            indent(f"  {WARN}Could not read file: {exc}{RST}")
            continue

    nl()
    indent(m("Messages will be appended to inbox.jsonl in the data directory."))
    indent(m("The relic:extract cron will process them on first run (requires LLM)."))
    nl()

    if state.backfill_count > 0:
        indent(f"{GOLD}Demo extraction preview{RST}")
        nl()
        indent(m("Run a keyword-heuristic pass now to preview what signals would be extracted."))
        indent(m("This uses no LLM - it is the same synthetic extractor as the demo."))
        nl()
        state.run_backfill_preview = confirm(
            "Run demo extraction preview on imported messages?",
            default=True,
        )
    else:
        state.run_backfill_preview = False  # type: ignore[attr-defined]


def step_confirm(state: State) -> None:
    header(8, TOTAL_STEPS)
    indent(b("Configuration Summary"))
    nl()
    indent(m("Review before installing. Press Ctrl+C to abort."))
    nl()
    hr()
    nl()

    rows = [
        ("Subject name",       state.subject_name),
        ("Subject ID",         state.subject_id),
        ("Telegram ID",        state.subject_telegram_id or m("(not set)")),
        ("Data directory",     state.data_dir),
        ("OpenClaw binary",    state.openclaw_bin),
        ("OpenClaw home",      state.openclaw_home),
        ("Hooks directory",    state.hooks_dir),
        ("Check-in window",    f"{state.checkin_hour_start}:00 – {state.checkin_hour_end}:59  "
                               f"every {state.checkin_interval_min} min"),
        ("Check-in schedule",  state.checkin_schedule),
        ("Relational agent",   state.relational_agent or m("(none)")),
        ("Telegram check-ins", gr("enabled") if state.enable_telegram else m("disabled")),
        ("Biofeedback",        gr("enabled") if state.enable_biofeedback else m("disabled")),
        ("Backfill",           (f"{gr(str(state.backfill_count) + ' messages')}  ←  "
                                f"{MUT}{state.backfill_path}{RST}")
                               if state.run_backfill else m("none")),
    ]

    col = max(len(k) for k, _ in rows) + 2
    for key, val in rows:
        indent(f"  {GOLD}{key.ljust(col)}{RST}  {WHT}{val}{RST}")

    nl()
    hr()
    nl()
    indent(m("Actions that will run:"))
    nl()

    actions = [
        f"Create runtime directory  {MUT}{state.data_dir}{RST}",
        "Write .env",
        "Compile + register hook: relic-capture",
        "Compile + register hook: relic-bootstrap",
    ]
    if state.run_backfill:
        actions.append(f"Import {state.backfill_count} messages → inbox.jsonl")
        if getattr(state, "run_backfill_preview", False):
            actions.append("Demo extraction preview (keyword heuristics)")
    for name, sched in [
        ("relic:extract",          "0 */2 * * *"),
        ("relic:checkin",          state.checkin_schedule),
        ("relic:passive-scan",     "0 */6 * * *"),
        ("relic:reply-extract",    "0 */6 * * *"),
        ("relic:synthesize",       "0 3 * * *"),
        ("relic:profile-sync",     "30 3 * * *"),
        ("relic:checkin-followup", "@manual"),
        ("+ 29 daily / weekly / monthly crons", "(see docs/CONFIGURATION.md)"),
    ]:
        actions.append(f"Create cron: {name}  {MUT}{sched}{RST}")

    for a in actions:
        indent(f"  {GOLDD}◈{RST}  {WHT}{a}{RST}")
    nl()

    if not confirm("Proceed with installation?"):
        abort()


def step_install(state: State) -> None:
    header(9, TOTAL_STEPS)
    indent(b("Installing"))
    nl()

    PAD = 54

    def task(label: str, fn) -> bool:
        print(f"  {GOLD}▶{RST}  {WHT}{label.ljust(PAD)}{RST}", end="", flush=True)
        if state.dry_run:
            print(f"  {MUT}skipped (dry run){RST}")
            return True
        try:
            fn()
            print(f"  {GRN}✓{RST}")
            return True
        except Exception as exc:
            msg = str(exc)[:80]
            print(f"  {RED}✗{RST}  {MUT}{msg}{RST}")
            state.failed_steps.append(label)
            return False

    def run_oc(*args: str, manual: str = "") -> None:
        result = subprocess.run([state.openclaw_bin, *args],
                                capture_output=True, text=True)
        if result.returncode != 0:
            msg = (result.stderr or result.stdout).strip()[:120]
            if manual:
                state.manual_steps.append(manual)
            raise RuntimeError(msg or f"exit {result.returncode}")

    # ── 1. Runtime directory ───────────────────────────────────────────────────
    def make_datadir():
        p = Path(state.data_dir)
        p.mkdir(parents=True, exist_ok=True)
        (p / "inbox.jsonl").touch(exist_ok=True)

    task("Create runtime directory", make_datadir)

    # ── 2. .env ────────────────────────────────────────────────────────────────
    task("Write .env", lambda: (REPO_ROOT / ".env").write_text(
        _build_env(state), encoding="utf-8"
    ))

    # ── 3. Hooks ───────────────────────────────────────────────────────────────
    nl()
    indent(m("OpenClaw hooks"))
    nl()

    for hook in ["relic-capture", "relic-bootstrap"]:
        hook_dir = REPO_ROOT / "hooks" / hook

        # compile step (npm install + tsc if tsconfig present)
        def compile_hook(hd: Path = hook_dir) -> None:
            if not (hd / "package.json").exists():
                return  # nothing to compile
            subprocess.run(["npm", "install", "--silent"],
                           cwd=hd, check=True, capture_output=True)
            if (hd / "tsconfig.json").exists():
                subprocess.run(["npx", "tsc", "--noEmit", "false"],
                               cwd=hd, check=True, capture_output=True)

        task(f"Compile hook: {hook}", compile_hook)

        # register with OpenClaw
        manual = (f"openclaw hooks enable {hook} --path {hook_dir}  "
                  f"# RELIC_SUBJECT_ID={state.subject_id}")
        task(
            f"Register hook: {hook}",
            lambda h=hook, hd=hook_dir, fb=manual: run_oc(
                "hooks", "enable", h, "--path", str(hd),
                "--env", f"RELIC_SUBJECT_ID={state.subject_id}",
                "--env", f"RELIC_DATA_DIR={state.data_dir}",
                manual=fb,
            ),
        )

    # ── 4. Backfill ────────────────────────────────────────────────────────────
    if state.run_backfill and state.backfill_path:
        nl()
        indent(m("Signal import"))
        nl()

        def import_messages() -> None:
            src = Path(state.backfill_path)
            dst = Path(state.data_dir) / "inbox.jsonl"
            lines = [l for l in src.read_text(encoding="utf-8").splitlines() if l.strip()]
            existing = dst.read_text(encoding="utf-8") if dst.exists() else ""
            existing_ids: set[str] = set()
            for el in existing.splitlines():
                try:
                    existing_ids.add(json.loads(el).get("message_id", ""))
                except Exception:
                    pass
            new_lines = []
            for line in lines:
                try:
                    obj = json.loads(line)
                    if obj.get("message_id") not in existing_ids:
                        new_lines.append(line)
                except Exception:
                    pass
            with open(dst, "a", encoding="utf-8") as f:
                for nl_line in new_lines:
                    f.write(nl_line + "\n")
            state.backfill_count = len(new_lines)  # update with actual imported count

        task(f"Import {state.backfill_count} messages → inbox.jsonl", import_messages)

        if getattr(state, "run_backfill_preview", False):
            def run_preview() -> None:
                sys.path.insert(0, str(REPO_ROOT / "src"))
                from relic.demo_runner import _extract_synthetic_observations  # type: ignore
                inbox = Path(state.data_dir) / "inbox.jsonl"
                messages = [
                    json.loads(l) for l in inbox.read_text(encoding="utf-8").splitlines()
                    if l.strip()
                ]
                observations = _extract_synthetic_observations(messages)
                # store for done screen
                state._preview_obs = observations  # type: ignore[attr-defined]

            ok = task("Demo extraction preview (keyword heuristics)", run_preview)
            if ok and not state.dry_run:
                obs = getattr(state, "_preview_obs", [])
                if obs:
                    nl()
                    indent(f"  {GRN}Extracted {len(obs)} synthetic signals{RST}")
                    facets_seen: dict[str, int] = {}
                    for o in obs:
                        facets_seen[o["facet_id"]] = facets_seen.get(o["facet_id"], 0) + 1
                    for fid, cnt in sorted(facets_seen.items(), key=lambda x: -x[1])[:6]:
                        indent(f"  {GOLDD}◈{RST}  {MUT}{fid}{RST}  {WHT}×{cnt}{RST}")

    # ── 5. Cron jobs ───────────────────────────────────────────────────────────
    nl()
    indent(m("OpenClaw cron jobs"))
    nl()

    python_bin = sys.executable
    src_dir    = str(REPO_ROOT / "src")
    env_flags  = [
        f"PYTHONPATH={src_dir}",
        f"RELIC_DATA_DIR={state.data_dir}",
        f"RELIC_SUBJECT_ID={state.subject_id}",
        f"RELIC_SUBJECT_NAME={state.subject_name}",
        f"RELIC_FOLLOWUP_CRON=relic:checkin-followup",
    ]
    if state.subject_telegram_id:
        env_flags.append(f"RELIC_TELEGRAM_ID={state.subject_telegram_id}")
    if state.relational_agent:
        env_flags.append(f"RELIC_RELATIONAL_AGENT={state.relational_agent}")

    # name → (schedule, python module)
    # Full cron set - matches the whitepaper operational schedule.
    # @manual crons are registered on-demand; they have no fixed schedule
    # but must exist as named crons so OpenClaw can invoke them by name.
    cron_defs: list[tuple[str, str, str]] = [
        # ── Core pipeline (always active) ────────────────────────────
        ("relic:extract",               "0 */2 * * *",          "relic.extract"),
        ("relic:checkin",               state.checkin_schedule, "relic.checkin"),
        ("relic:passive-scan",          "0 */6 * * *",          "relic.passive_scan"),
        ("relic:reply-extract",         "0 */6 * * *",          "relic.reply_extract"),
        ("relic:synthesize",            "0 3 * * *",            "relic.synthesize"),
        ("relic:profile-sync",          "30 3 * * *",           "relic.profile_sync"),
        ("relic:checkin-followup",      "@manual",              "relic.checkin_followup"),
        # ── Daily enrichment ─────────────────────────────────────────
        ("relic:entity-extract",        "0 4 * * *",            "relic.entity_extract"),
        ("relic:decisions",             "15 4 * * *",           "relic.decisions"),
        ("relic:healthcheck",           "0 4 * * *",            "relic.healthcheck"),
        ("relic:memory",                "0 5 * * 0",            "relic.memory"),
        # ── Biofeedback (enable if hardware present) ─────────────────
        ("relic:biofeedback-pull",      "5 4 * * *",            "relic.biofeedback"),
        ("relic:biofeedback-gadgetbridge", "10 4 * * *",        "relic.biofeedback_gadgetbridge"),
        ("relic:biofeedback-gb-ingest", "@manual",              "relic.biofeedback_gb_ingest"),
        ("relic:muse-aggregate",        "30 4 * * *",           "relic.muse_aggregate"),
        ("relic:muse-recorder",         "@manual",              "relic.muse_recorder"),
        # ── Weekly analysis ───────────────────────────────────────────
        ("relic:liwc",                  "0 3 * * 0",            "relic.liwc"),
        ("relic:stress-index",          "0 6 * * 1",            "relic.stress_index"),
        # ── Optional integrations ─────────────────────────────────────
        ("relic:budget-bridge",         "20 4 * * *",           "relic.budget_bridge"),
        ("relic:voicenote",             "@manual",              "relic.voicenote"),
        ("relic:domain-prober",         "@manual",              "relic.domain_prober"),
        ("relic:backfill",              "@manual",              "relic.backfill"),
        ("relic:motives",               "@manual",              "relic.motives"),
        # ── Monthly specialist analyzers ──────────────────────────────
        ("relic:schemas",               "0 5 1 * *",            "relic.schemas"),
        ("relic:goals",                 "30 5 1 * *",           "relic.goals"),
        ("relic:sdt",                   "0 6 1 * *",            "relic.sdt"),
        ("relic:portrait",              "0 6 1 * *",            "relic.portrait"),
        ("relic:idiolect",              "0 4 1 * *",            "relic.idiolect"),
        ("relic:caps",                  "30 5 2 * *",           "relic.caps"),
        ("relic:attachment",            "0 5 3 * *",            "relic.attachment"),
        ("relic:defenses",              "30 5 3 * *",           "relic.defenses"),
        ("relic:narrative",             "0 6 3 * *",            "relic.narrative"),
        ("relic:appraisal",             "30 4 5 * *",           "relic.appraisal"),
        ("relic:mental-models",         "0 5 5 * *",            "relic.mental_models"),
        ("relic:dual-process",          "30 5 5 * *",           "relic.dual_process"),
        ("relic:constructs",            "0 6 5 * *",            "relic.constructs"),
    ]

    for cron_name, schedule, module in cron_defs:
        cmd = f"{python_bin} -m {module}"
        env_args: list[str] = []
        for ev in env_flags:
            env_args += ["--env", ev]
        sched_args = ["--schedule", schedule] if schedule != "@manual" else ["--on-demand"]
        manual_cmd = (
            f"openclaw cron add {cron_name} --command \"{cmd}\" "
            f"--cwd \"{REPO_ROOT}\" --schedule \"{schedule}\""
        )
        task(
            f"Register cron: {cron_name}",
            lambda n=cron_name, c=cmd, sa=sched_args, ea=env_args, fb=manual_cmd: run_oc(
                "cron", "add", n,
                "--command", c,
                "--cwd", str(REPO_ROOT),
                *sa,
                *ea,
                manual=fb,
            ),
        )

    nl()


def step_done(state: State) -> None:
    header()
    nl()

    if not state.failed_steps:
        center(f"{GRN}{BOLD}Installation complete.{RST}")
    else:
        center(f"{WARN}{BOLD}Installation completed with warnings.{RST}")

    nl()
    hr("═")
    nl()

    indent(b("Next steps:"))
    nl()

    next_steps = [
        ("Verify the demo pipeline",
         "python -m relic.demo_runner --output-dir demo/generated"),
        ("Open the Arasaka demo console",
         "open demo/generated/demo_console.html"),
        ("Check hook status",
         "openclaw hooks status"),
        ("Check cron status",
         "openclaw cron status"),
    ]
    if state.run_backfill and state.backfill_count:
        next_steps.insert(2, (
            "Verify inbox import",
            f"wc -l {state.data_dir}/inbox.jsonl",
        ))

    for label, cmd in next_steps:
        indent(f"  {GOLD}◈{RST}  {WHT}{label}{RST}")
        indent(f"       {MUT}{cmd}{RST}")
        nl()

    indent(m("Connect an LLM provider to activate the extraction pipeline:"))
    indent(f"  {MUT}docs/ADAPTERS.md  ·  implement ProviderLLMClient.complete(){RST}")
    nl()
    indent(m("Once configured, extraction runs automatically on the next cron cycle."))
    nl()

    if state.manual_steps:
        hr("·")
        nl()
        indent(wa("The following steps need to be run manually:"))
        nl()
        for s in state.manual_steps:
            indent(f"  {WARN}▶{RST}  {WHT}{s}{RST}")
        nl()
        indent(m("These commands failed during installation - OpenClaw may require"))
        indent(m("a different syntax on your version. See hooks/*/HOOK.md for details."))
        nl()

    hr("═")
    nl()
    center(f"{GOLD}SECURE YOUR SOUL{RST}  {GOLDD}·{RST}  {MUT}荒坂 CORP · RELIC{RST}")
    nl()


# ── Config file builder ────────────────────────────────────────────────────────

def _build_env(state: State) -> str:
    lines = [
        "# Relic - generated by install.py",
        f"# Hermes Agent {TESTED_HERMES} · {time.strftime('%Y-%m-%d')}",
        "",
        "# ── Subject ──────────────────────────────────────────────",
        f"RELIC_SUBJECT_ID={state.subject_id}",
        f"RELIC_SUBJECT_NAME={state.subject_name}",
    ]
    if state.subject_telegram_id:
        lines.append(f"RELIC_TELEGRAM_ID={state.subject_telegram_id}")
    lines += [
        "",
        "# ── Paths ────────────────────────────────────────────────",
        f"RELIC_DATA_DIR={state.data_dir}",
        f"HERMES_HOME={state.hermes_home}",
        f"HERMES_BIN={state.hermes_bin}",
        "",
        "# ── Check-in schedule ───────────────────────────────────",
        f"RELIC_CHECKIN_HOUR_START={state.checkin_hour_start}",
        f"RELIC_CHECKIN_HOUR_END={state.checkin_hour_end}",
        f"RELIC_CHECKIN_INTERVAL_MIN={state.checkin_interval_min}",
        f"# Resulting cron: {state.checkin_schedule}",
        "",
        "# ── Cron identifiers ────────────────────────────────────",
        "RELIC_FOLLOWUP_CRON=relic:checkin-followup",
        "",
        "# ── Optional integrations ───────────────────────────────",
        f"RELIC_ENABLE_TELEGRAM={'true' if state.enable_telegram else 'false'}",
        f"RELIC_ENABLE_BIOFEEDBACK={'true' if state.enable_biofeedback else 'false'}",
    ]
    if state.relational_agent:
        lines += [
            "",
            "# ── Relational agent ────────────────────────────────",
            f"RELIC_RELATIONAL_AGENT={state.relational_agent}",
        ]
        if state.relational_agent_ids:
            lines.append(f"RELIC_RELATIONAL_AGENT_IDS={state.relational_agent_ids}")
    lines += [
        "",
        "# ── LLM provider ────────────────────────────────────────",
        "# Set these to connect Relic to your LLM backend.",
        "# See docs/ADAPTERS.md for the implementation contract.",
        "RELIC_MODEL=",
        "RELIC_PROVIDER=",
        "",
        "# ── Biofeedback (Zepp/Amazfit) ──────────────────────────",
        "RELIC_ZEPP_EMAIL=",
        "RELIC_ZEPP_PASSWORD=",
    ]
    if state.enable_telegram or state.enable_biofeedback:
        lines += [
            "",
            "# ── Telegram ─────────────────────────────────────────",
            "# Required for check-in delivery. Create a bot via @BotFather.",
            "TELEGRAM_BOT_TOKEN=",
            "TELEGRAM_LOGS_CHAT_ID=",
            "TELEGRAM_LOGS_THREAD_ID=",
        ]
    if state.enable_paperclip and state.paperclip_company_id:
        lines += [
            "",
            "# ── Paperclip ───────────────────────────────────────────",
            f"PAPERCLIP_API_URL={state.paperclip_url}",
            f"PAPERCLIP_COMPANY_ID={state.paperclip_company_id}",
        ]
        if state.paperclip_bio_analyst_key:
            lines += [
                f"PAPERCLIP_BIO_ANALYST_KEY={state.paperclip_bio_analyst_key}",
                f"PAPERCLIP_BIO_REVIEWER_ID={state.paperclip_bio_reviewer_id}",
            ]
        if state.paperclip_inq_analyst_key:
            lines += [
                f"PAPERCLIP_INQ_ANALYST_KEY={state.paperclip_inq_analyst_key}",
                f"PAPERCLIP_INQ_REVIEWER_ID={state.paperclip_inq_reviewer_id}",
            ]
        if state.paperclip_health_analyst_key:
            lines += [
                f"PAPERCLIP_HEALTH_ANALYST_KEY={state.paperclip_health_analyst_key}",
                f"PAPERCLIP_HEALTH_REVIEWER_ID={state.paperclip_health_reviewer_id}",
            ]
        if state.paperclip_humanness_analyst_key:
            lines += [
                f"PAPERCLIP_HUMANNESS_ANALYST_KEY={state.paperclip_humanness_analyst_key}",
                f"PAPERCLIP_HUMANNESS_REVIEWER_ID={state.paperclip_humanness_reviewer_id}",
            ]
    elif state.enable_paperclip:
        lines += [
            "",
            "# ── Paperclip (run setup_paperclip.py to populate) ─────",
            "PAPERCLIP_API_URL=http://localhost:3100",
            "PAPERCLIP_COMPANY_ID=",
            "PAPERCLIP_BIO_ANALYST_KEY=",
            "PAPERCLIP_BIO_REVIEWER_ID=",
            "PAPERCLIP_INQ_ANALYST_KEY=",
            "PAPERCLIP_INQ_REVIEWER_ID=",
            "PAPERCLIP_HEALTH_ANALYST_KEY=",
            "PAPERCLIP_HEALTH_REVIEWER_ID=",
            "PAPERCLIP_HUMANNESS_ANALYST_KEY=",
            "PAPERCLIP_HUMANNESS_REVIEWER_ID=",
        ]
    return "\n".join(lines) + "\n"


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Relic installation wizard.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview all steps without writing files or running commands.",
    )
    args = parser.parse_args()

    state = State(dry_run=args.dry_run)

    try:
        step_welcome(state)
        step_prereqs(state)
        step_subject(state)
        step_datadir(state)
        step_hermes(state)
        step_checkin(state)
        step_integrations(state)
        step_backfill(state)
        step_confirm(state)
        step_install(state)
        step_done(state)
    except KeyboardInterrupt:
        nl(2)
        abort()


if __name__ == "__main__":
    main()
