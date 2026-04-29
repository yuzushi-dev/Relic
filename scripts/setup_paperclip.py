#!/usr/bin/env python3
"""Interactive setup: Relic × Paperclip integration.

Creates a Paperclip company with the analysis agents you choose, then
prints the environment variables you need to add to your .env.

Prerequisites:
  1. Paperclip installed: npm install -g paperclipai
  2. Paperclip running:   npx paperclipai run   (keep open in another terminal)

Usage:
  python3 scripts/setup_paperclip.py [--api-url http://localhost:3100]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone


def _agent_env(extra: dict | None = None) -> dict:
    """Build env dict for a Paperclip process agent.

    Always injects RELIC_DATA_DIR (if set in the parent env) so agents can
    write override files and state to the correct location rather than
    falling back to the source tree.
    """
    env: dict = {"PYTHONPATH": "src"}
    relic_data_dir = os.environ.get("RELIC_DATA_DIR", "")
    if relic_data_dir:
        env["RELIC_DATA_DIR"] = relic_data_dir
    if extra:
        env.update(extra)
    return env


def _gemini_agent_config(timeout_sec: int = 300) -> dict:
    """Gemini primary with Paperclip-managed Hermes fallback on quota limits."""
    return {
        "model": "gemini-2.5-flash",
        "timeoutSec": timeout_sec,
        "command": os.environ.get(
            "PAPERCLIP_GEMINI_FALLBACK_COMMAND",
            "paperclip-gemini-fallback",
        ),
        "env": {
            "PAPERCLIP_HERMES_FALLBACKS": os.environ.get(
                "PAPERCLIP_HERMES_FALLBACKS",
                "ollama-cloud:gpt-oss:20b,openrouter:openrouter/free",
            ),
            "PAPERCLIP_HERMES_FALLBACK_TIMEOUT_SEC": "180",
            "PAPERCLIP_HERMES_FALLBACK_MAX_TURNS": "12",
        },
    }


# ── API helpers ───────────────────────────────────────────────────────────────

def _api(method: str, path: str, base_url: str, token: str = "", data: dict | None = None) -> dict:
    body = json.dumps(data).encode() if data is not None else None
    headers: dict = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        f"{base_url}/api{path}",
        data=body,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        body_text = e.read().decode()[:300]
        raise RuntimeError(f"HTTP {e.code} on {method} {path}: {body_text}") from e


# ── Agent definitions ──────────────────────────────────────────────────────────

BIO_AGENTS = [
    {
        "slug": "bio_analyst",
        "spec": {
            "name": "Biofeedback Analyst",
            "capabilities": (
                "Runs nightly Spearman correlation analysis between physiological "
                "signals (HRV, sleep, stress) and text-derived personality facet "
                "observations. Detects bio-linguistic divergences."
            ),
            "adapterType": "process",
            "adapterConfig": {
                "command": "python3",
                "args": ["-m", "mnemon.biofeedback_correlation"],
                "env": _agent_env(),
                "timeoutSec": 600,
            },
        },
        "heartbeat": {"enabled": True, "intervalSec": 86400, "maxConcurrentRuns": 1},
        "key_name": "relic-bio-analyst",
    },
    {
        "slug": "bio_reviewer",
        "spec": {
            "name": "Biofeedback Reviewer",
            "capabilities": (
                "Reviews biofeedback correlation results. Evaluates statistical "
                "significance, bio-linguistic divergences, and flags confirmed or "
                "inconclusive findings for human attention."
            ),
            "adapterType": "gemini_local",
            "adapterConfig": _gemini_agent_config(300),
        },
        "heartbeat": {"enabled": True, "intervalSec": 600, "maxConcurrentRuns": 1},
        "key_name": None,
    },
]

INQ_AGENTS = [
    {
        "slug": "inq_analyst",
        "spec": {
            "name": "Inquiry Analyst",
            "capabilities": (
                "Runs structured deliberation hypothesis verification on behavioral and "
                "conversational observations. Submits structured findings as "
                "Paperclip issues."
            ),
            "adapterType": "process",
            "adapterConfig": {
                "command": "python3",
                "args": ["-m", "mnemon.relic_inquiry_team"],
                "env": _agent_env({"RELIC_INQUIRY_TEAM": "true"}),
                "timeoutSec": 600,
            },
        },
        "heartbeat": {"enabled": True, "intervalSec": 86400, "maxConcurrentRuns": 1},
        "key_name": "relic-inq-analyst",
    },
    {
        "slug": "inq_reviewer",
        "spec": {
            "name": "Inquiry Reviewer",
            "capabilities": (
                "Reviews personality and behavioral findings. Evaluates evidence "
                "quality, cross-references observations, and proposes "
                "confirmed/inconclusive/false-positive verdicts."
            ),
            "adapterType": "gemini_local",
            "adapterConfig": _gemini_agent_config(300),
        },
        "heartbeat": {"enabled": True, "intervalSec": 600, "maxConcurrentRuns": 1},
        "key_name": None,
    },
]



HEALTH_AGENTS = [
    {
        "slug": "health_analyst",
        "spec": {
            "name": "Health Analyst",
            "capabilities": (
                "Runs every 12 hours. Computes model health metrics "
                "(avg_confidence, coverage, bootstrap_loop_risk), identifies "
                "neglected facets, and submits a structured health issue for review."
            ),
            "adapterType": "process",
            "adapterConfig": {
                "command": "python3",
                "args": ["-m", "mnemon.health_monitor"],
                "env": _agent_env(),
                "timeoutSec": 120,
            },
        },
        "heartbeat": {"enabled": True, "intervalSec": 43200, "maxConcurrentRuns": 1},
        "key_name": "relic-health-analyst",
    },
    {
        "slug": "health_strategist",
        "spec": {
            "name": "Health Strategist",
            "capabilities": (
                "Reviews health reports. Evaluates confidence/coverage trends "
                "and bootstrap loop risk, and proposes concrete interventions "
                "to stabilize the model."
            ),
            "adapterType": "gemini_local",
            "adapterConfig": _gemini_agent_config(300),
        },
        "heartbeat": {"enabled": True, "intervalSec": 600, "maxConcurrentRuns": 1},
        "key_name": None,
    },
]



HUMANNESS_AGENTS = [
    {
        "slug": "humanness_analyst",
        "spec": {
            "name": "Humanness Analyst",
            "capabilities": (
                "Runs daily. Analyzes recent relational-agent messages for AI tell-tale patterns "
                "(em dash, bullet points, bot phrases, affirmation→question structure, "
                "disproportionate length, emoji monotony). Computes per-pattern scores, "
                "selects worst-case samples for qualitative review, and submits a structured "
                "Paperclip issue with a LLM-as-judge rubric for the reviewer."
            ),
            "adapterType": "process",
            "adapterConfig": {
                "command": "python3",
                "args": ["-m", "mnemon.humanness_monitor"],
                "env": _agent_env(),
                "timeoutSec": 120,
            },
        },
        "heartbeat": {"enabled": True, "intervalSec": 86400, "maxConcurrentRuns": 1},
        "key_name": "relic-humanness-analyst",
    },
    {
        "slug": "humanness_reviewer",
        "spec": {
            "name": "Humanness Reviewer",
            "capabilities": (
                "Reviews humanness reports using LLM-as-judge methodology. Reads sample "
                "relational-agent messages and scores them on 4 dimensions (naturalness, "
                "proportionality, continuity, directness) against the agent's style rubric. "
                "Proposes specific interventions: forbidden phrases, persona updates, style overlays."
            ),
            "adapterType": "gemini_local",
            "adapterConfig": _gemini_agent_config(300),
        },
        "heartbeat": {"enabled": True, "intervalSec": 600, "maxConcurrentRuns": 1},
        "key_name": None,
    },
]


DIRECTOR_AGENTS = [
    {
        "slug": "strategic_director",
        "spec": {
            "name": "Strategic Director",
            "capabilities": (
                "Synthesizes weekly findings from all four operational teams (Health, "
                "Humanness, Biofeedback, Inquiry). Identifies convergences and contradictions, "
                "assesses scientific validity, and produces a DIRECTION.md with concrete "
                "objectives for the next cycle."
            ),
            "adapterType": "process",
            "adapterConfig": {
                "command": "python3",
                "args": ["-m", "mnemon.strategic_director"],
                "env": _agent_env(),
                "timeoutSec": 600,
            },
        },
        "heartbeat": {"enabled": True, "intervalSec": 604800, "maxConcurrentRuns": 1},
        "key_name": None,
    },
]

CEO_AGENTS = [
    {
        "slug": "ceo",
        "spec": {
            "name": "CEO",
            "role": "ceo",
            "capabilities": (
                "Reads daily digests from all operational and research teams "
                "(Health, Humanness, Biofeedback, Inquiry, R&D, Dev, Manuscript, Docs). "
                "Identifies priorities, resolves conflicts between teams, assigns new issues "
                "to the appropriate team, and posts a brief daily status summary."
            ),
            "adapterType": "gemini_local",
            "adapterConfig": _gemini_agent_config(300),
        },
        "heartbeat": {"enabled": True, "intervalSec": 86400, "maxConcurrentRuns": 1},
        "key_name": None,
    },
]

RD_AGENTS = [
    {
        "slug": "rd_analyst",
        "spec": {
            "name": "R&D Analyst",
            "role": "engineer",
            "capabilities": (
                "Scans ArXiv and Reddit every 5 hours for papers and discussions relevant to Relic. "
                "Relevance criteria: computational personality modeling, biofeedback×AI "
                "correlations (HRV/sleep/stress), multi-agent coordination, LLM humanness "
                "and AI-pattern detection, companion AI and relational agents. "
                "Summarizes each relevant finding in a structured Paperclip issue with: "
                "title, source URL, one-paragraph summary, and relevance tag."
            ),
            "adapterType": "gemini_local",
            "adapterConfig": _gemini_agent_config(600),
        },
        "heartbeat": {"enabled": True, "intervalSec": 18000, "maxConcurrentRuns": 1},
        "key_name": None,
    },
]

DEV_AGENTS = [
    {
        "slug": "dev_planner",
        "spec": {
            "name": "Dev Planner",
            "role": "engineer",
            "capabilities": (
                "Reads open issues tagged for the Dev team in the Relic OSS repository "
                "(src/relic/, src/lib/, tests/). Produces a structured implementation plan "
                "for each issue: files to change, approach, edge cases, test strategy. "
                "Assigns the plan as a sub-issue to Dev Engineer for execution."
            ),
            "adapterType": "codex_local",
            "adapterConfig": {"model": "gpt-5.4-mini", "timeoutSec": 300},
        },
        "heartbeat": {"enabled": True, "intervalSec": 43200, "maxConcurrentRuns": 1},
        "key_name": None,
    },
    {
        "slug": "dev_engineer",
        "spec": {
            "name": "Dev Engineer",
            "role": "engineer",
            "capabilities": (
                "Implements code changes in the Relic OSS repository based on plans "
                "produced by Dev Planner. Writes or updates src/relic/, src/lib/, and "
                "tests/ files. Runs pytest before marking an issue resolved. "
                "Never commits directly to master — opens a branch and reports diff."
            ),
            "adapterType": "gemini_local",
            "adapterConfig": _gemini_agent_config(600),
        },
        "heartbeat": {"enabled": True, "intervalSec": 43200, "maxConcurrentRuns": 1},
        "key_name": None,
    },
]

MANUSCRIPT_AGENTS = [
    {
        "slug": "manuscript_editor",
        "spec": {
            "name": "Manuscript Editor",
            "role": "pm",
            "capabilities": (
                "Maintains the PACMHCI manuscript at ~/relic-paper-package/. "
                "Reads open issues from Health, Humanness, Biofeedback, Inquiry, and R&D teams. "
                "Updates pacmhci-manuscript-draft-v1.md only when new findings differ from "
                "what is already written — no rewrites for style, only delta-driven additions. "
                "Logs every change as a brief note in the issue thread."
            ),
            "adapterType": "gemini_local",
            "adapterConfig": _gemini_agent_config(600),
        },
        "heartbeat": {"enabled": True, "intervalSec": 604800, "maxConcurrentRuns": 1},
        "key_name": None,
    },
]

DOCS_AGENTS = [
    {
        "slug": "docs_writer",
        "spec": {
            "name": "Docs Writer",
            "role": "designer",
            "capabilities": (
                "Maintains documentation for the Relic OSS project. "
                "Public docs (README, usage guides, .env.example): must never contain PII, "
                "real names, absolute paths, or private credentials. "
                "Internal technical docs (architecture, design decisions, module guides): "
                "kept in docs/ and updated when source code changes. "
                "Triggered by Dev Engineer issues or structural changes in src/."
            ),
            "adapterType": "gemini_local",
            "adapterConfig": _gemini_agent_config(300),
        },
        "heartbeat": {"enabled": True, "intervalSec": 604800, "maxConcurrentRuns": 1},
        "key_name": None,
    },
]

COMITATO_AGENTS = [
    {
        "slug": "comitato",
        "spec": {
            "name": "Comitato",
            "role": "pm",
            "capabilities": (
                "Reviews R&D innovation proposals ([Proposal] issues). "
                "Evaluates each proposal on 3 criteria: relevance to Relic goals "
                "(personality, humanness, biofeedback), technical feasibility in the "
                "current codebase, and clear priority over existing work. "
                "Approved proposals become [Dev] issues for the Dev team. "
                "Rejected proposals receive a detailed explanation."
            ),
            "adapterType": "gemini_local",
            "adapterConfig": _gemini_agent_config(300),
        },
        "heartbeat": {"enabled": True, "intervalSec": 21600, "maxConcurrentRuns": 1},
        "key_name": None,
    },
]



# ── Setup flow ────────────────────────────────────────────────────────────────

def check_paperclip(base_url: str) -> str:
    try:
        health = _api("GET", "/health", base_url)
        version = health.get("version", "?")
        print(f"  Paperclip {version} — OK")
        return version
    except Exception as exc:
        print(f"\n  ERROR: cannot reach Paperclip at {base_url}")
        print(f"  {exc}")
        print(f"\n  Start it first:  npx paperclipai run")
        sys.exit(1)


_VALID_CHOICES = frozenset("abihndcrvmok")


def ask_pipelines() -> str:
    print()
    print("Which pipelines do you want to enable?")
    print("  ── Operational teams (process adapters) ──")
    print("  [b]  Biofeedback Correlation  — nightly HRV/sleep/stress × personality")
    print("  [i]  Inquiry Verification     — structured deliberation hypothesis verification")
    print("  [h]  Health Monitor           — every 12h confidence/coverage/loop-risk")
    print("  [n]  Humanness Monitor        — daily AI-pattern detection + LLM-as-judge review")
    print("  [d]  Strategic Director       — weekly synthesis + direction across all teams")
    print("  ── Management & research (gemini_local / codex_local) ──")
    print("  [c]  CEO                      — daily cross-team coordination (gemini_local)")
    print("  [r]  R&D Analyst              — every 5h ArXiv scan + proposals (gemini_local)")
    print("  [k]  Comitato                 — every 6h R&D proposal review (gemini_local)")
    print("  [v]  Dev Team                 — every 12h planner (codex_local) + engineer (gemini_local)")
    print("  [m]  Manuscript Editor        — weekly delta-driven manuscript updates (gemini_local)")
    print("  [o]  Docs Writer              — weekly OSS + internal docs (gemini_local)")
    print("  [a]  All                      (default)")
    print("  [q]  Skip / quit")
    print()
    choice = input("Choice [a]: ").strip().lower() or "a"
    if choice == "q":
        print("Skipped.")
        sys.exit(0)
    if choice not in _VALID_CHOICES:
        print(f"Unknown choice '{choice}'. Defaulting to all.")
        choice = "a"
    return choice


def create_company(base_url: str) -> tuple[str, str]:
    name = input("\nCompany name [Relic]: ").strip() or "Relic"
    goal = (
        "Scientific analysis of biofeedback↔personality correlations and "
        "structured deliberation verification of behavioral findings."
    )
    company = _api("POST", "/companies", base_url, data={"name": name, "goal": goal})
    cid = company["id"]
    print(f"  Company '{name}' created — {cid[:8]}…")
    return cid, name


def create_agents(
    base_url: str,
    company_id: str,
    agent_defs: list[dict],
) -> dict[str, dict]:
    results: dict[str, dict] = {}
    for defn in agent_defs:
        agent = _api(
            "POST",
            f"/companies/{company_id}/agents",
            base_url,
            data=defn["spec"],
        )
        agent_id = agent["id"]

        _api("PATCH", f"/agents/{agent_id}", base_url, data={
            "runtimeConfig": {"heartbeat": defn["heartbeat"]},
        })

        token: str | None = None
        if defn["key_name"]:
            from subprocess import run, PIPE
            result = run(
                [
                    sys.executable, "-m", "pip", "show", "paperclipai",
                ],
                stdout=PIPE, stderr=PIPE,
            )
            # Use npx CLI to generate key
            import subprocess, shutil
            npx = shutil.which("npx")
            if npx:
                out = subprocess.run(
                    [
                        npx, "paperclipai", "agent", "local-cli",
                        agent["urlKey"],
                        "-C", company_id,
                        "--key-name", defn["key_name"],
                        "--no-install-skills",
                        "--api-base", base_url,
                        "--json",
                    ],
                    capture_output=True, text=True,
                )
                if out.returncode == 0:
                    key_data = json.loads(out.stdout)
                    token = key_data["key"]["token"]

        results[defn["slug"]] = {"id": agent_id, "name": defn["spec"]["name"], "token": token}
        print(f"  {defn['spec']['name']} — {agent_id[:8]}…"
              + (f"  key={token[:16]}…" if token else ""))
    return results


def print_env(base_url: str, company_id: str, agents: dict[str, dict], choice: str) -> None:
    print()
    print("─" * 60)
    print("Add these to your .env:")
    print("─" * 60)
    print(f"PAPERCLIP_API_URL={base_url}")
    print(f"PAPERCLIP_COMPANY_ID={company_id}")

    if choice in ("a", "b"):
        bio_a = agents.get("bio_analyst", {})
        bio_r = agents.get("bio_reviewer", {})
        if bio_a.get("token"):
            print(f"PAPERCLIP_BIO_ANALYST_KEY={bio_a['token']}")
        if bio_r.get("id"):
            print(f"PAPERCLIP_BIO_REVIEWER_ID={bio_r['id']}")

    if choice in ("a", "i"):
        inq_a = agents.get("inq_analyst", {})
        inq_r = agents.get("inq_reviewer", {})
        if inq_a.get("token"):
            print(f"PAPERCLIP_INQ_ANALYST_KEY={inq_a['token']}")
        if inq_r.get("id"):
            print(f"PAPERCLIP_INQ_REVIEWER_ID={inq_r['id']}")

    if choice in ("a", "h"):
        ha = agents.get("health_analyst", {})
        hs = agents.get("health_strategist", {})
        if ha.get("token"):
            print(f"PAPERCLIP_HEALTH_ANALYST_KEY={ha['token']}")
        if hs.get("id"):
            print(f"PAPERCLIP_HEALTH_REVIEWER_ID={hs['id']}")

    if choice in ("a", "n"):
        hu_a = agents.get("humanness_analyst", {})
        hu_r = agents.get("humanness_reviewer", {})
        if hu_a.get("token"):
            print(f"PAPERCLIP_HUMANNESS_ANALYST_KEY={hu_a['token']}")
        if hu_r.get("id"):
            print(f"PAPERCLIP_HUMANNESS_REVIEWER_ID={hu_r['id']}")

    if choice in ("a", "d"):
        sd = agents.get("strategic_director", {})
        if sd.get("id"):
            print(f"PAPERCLIP_DIRECTOR_ID={sd['id']}")

    if choice in ("a", "c"):
        ceo = agents.get("ceo", {})
        if ceo.get("id"):
            print(f"PAPERCLIP_CEO_ID={ceo['id']}")

    if choice in ("a", "r"):
        rd = agents.get("rd_analyst", {})
        if rd.get("id"):
            print(f"PAPERCLIP_RD_ANALYST_ID={rd['id']}")

    if choice in ("a", "v"):
        dp = agents.get("dev_planner", {})
        de = agents.get("dev_engineer", {})
        if dp.get("id"):
            print(f"PAPERCLIP_DEV_PLANNER_ID={dp['id']}")
        if de.get("id"):
            print(f"PAPERCLIP_DEV_ENGINEER_ID={de['id']}")

    if choice in ("a", "m"):
        me = agents.get("manuscript_editor", {})
        if me.get("id"):
            print(f"PAPERCLIP_MANUSCRIPT_ID={me['id']}")

    if choice in ("a", "o"):
        dw = agents.get("docs_writer", {})
        if dw.get("id"):
            print(f"PAPERCLIP_DOCS_ID={dw['id']}")

    if choice in ("a", "k"):
        co = agents.get("comitato", {})
        if co.get("id"):
            print(f"PAPERCLIP_COMITATO_ID={co['id']}")

    print("─" * 60)
    print()
    print("Paperclip UI: http://localhost:3100")
    print()


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Relic × Paperclip setup")
    parser.add_argument(
        "--api-url",
        default="http://localhost:3100",
        help="Paperclip API base URL (default: http://localhost:3100)",
    )
    args = parser.parse_args()
    base_url = args.api_url.rstrip("/")

    print()
    print("Relic × Paperclip setup")
    print("=" * 40)
    print()
    print("Checking Paperclip…")
    check_paperclip(base_url)

    choice = ask_pipelines()
    print()
    print("Creating company…")
    company_id, _ = create_company(base_url)

    agents: dict[str, dict] = {}
    defs: list[dict] = []
    if choice in ("a", "b"):
        defs += BIO_AGENTS
    if choice in ("a", "i"):
        defs += INQ_AGENTS
    if choice in ("a", "h"):
        defs += HEALTH_AGENTS
    if choice in ("a", "n"):
        defs += HUMANNESS_AGENTS
    if choice in ("a", "d"):
        defs += DIRECTOR_AGENTS
    if choice in ("a", "c"):
        defs += CEO_AGENTS
    if choice in ("a", "r"):
        defs += RD_AGENTS
    if choice in ("a", "v"):
        defs += DEV_AGENTS
    if choice in ("a", "m"):
        defs += MANUSCRIPT_AGENTS
    if choice in ("a", "o"):
        defs += DOCS_AGENTS
    if choice in ("a", "k"):
        defs += COMITATO_AGENTS
    print("Creating agents…")
    agents = create_agents(base_url, company_id, defs)

    print_env(base_url, company_id, agents, choice)


if __name__ == "__main__":
    main()
