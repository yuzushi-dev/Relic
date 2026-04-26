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
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone


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
                "args": ["-m", "relic.biofeedback_correlation"],
                "env": {"PYTHONPATH": "src"},
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
            "adapterConfig": {"model": "gemini-2.5-flash", "timeoutSec": 300},
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
                "args": ["-m", "relic.relic_inquiry_team"],
                "env": {"PYTHONPATH": "src", "RELIC_INQUIRY_TEAM": "true"},
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
            "adapterConfig": {"model": "gemini-2.5-flash", "timeoutSec": 300},
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
                "args": ["-m", "relic.health_monitor"],
                "env": {"PYTHONPATH": "src"},
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
            "adapterConfig": {"model": "gemini-2.5-flash", "timeoutSec": 300},
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
                "args": ["-m", "relic.humanness_monitor"],
                "env": {"PYTHONPATH": "src"},
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
            "adapterConfig": {"model": "gemini-2.5-flash", "timeoutSec": 300},
        },
        "heartbeat": {"enabled": True, "intervalSec": 600, "maxConcurrentRuns": 1},
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


def ask_pipelines() -> str:
    print()
    print("Which pipelines do you want to enable?")
    print("  [b]  Biofeedback Correlation  — nightly HRV/sleep/stress × personality")
    print("  [i]  Inquiry Verification     — structured deliberation hypothesis verification")
    print("  [h]  Health Monitor           — every 12h confidence/coverage/loop-risk")
    print("  [n]  Humanness Monitor        — daily AI-pattern detection + LLM-as-judge review")
    print("  [a]  All four                 (default)")
    print("  [q]  Skip / quit")
    print()
    choice = input("Choice [a]: ").strip().lower() or "a"
    if choice == "q":
        print("Skipped.")
        sys.exit(0)
    if choice not in ("a", "b", "i", "h", "n"):
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

    print("Creating agents…")
    agents = create_agents(base_url, company_id, defs)

    print_env(base_url, company_id, agents, choice)


if __name__ == "__main__":
    main()
