#!/usr/bin/env python3
"""Relic Humanness Analyst — measures how human the relational agent sounds in chat.

Detects typical LLM patterns in recent relational-agent messages:
em dash, bullet point, frasi da chatbot, struttura affermazione→domanda,
lunghezza sproporzionata, emoji monotone.

Sottomette un report strutturato a Paperclip per valutazione qualitativa
LLM-as-judge da parte di humanness_reviewer (gemini).

Cron entrypoint: relic:humanness-monitor
Schedule: 0 8 * * *  (ogni giorno alle 08:00)
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from lib.relic_debate import run_debate
from lib.reviewer_workspace import export_debate

SCRIPT = "relic_humanness_analyst"

RELIC_DIR = Path(
    os.environ.get("RELIC_DATA_DIR")
    or str(Path(__file__).resolve().parents[1] / "relic")
)
HERMES_PROFILE_DIR = Path(os.environ.get("HERMES_PROFILE_DIR", ""))
HUMANNESS_OVERRIDES_FILE = RELIC_DIR / "humanness_overrides.json"

# ── Soglie ────────────────────────────────────────────────────────────────────

EMDASH_RATE_WARN = 0.05        # em dash per 100 char
EMDASH_RATE_CRIT = 0.15
BULLET_RATE_WARN = 0.10        # frazione messaggi con bullet
BULLET_RATE_CRIT = 0.25
BOT_PHRASE_RATE_WARN = 0.05    # frazione messaggi con frasi chatbot
BOT_PHRASE_RATE_CRIT = 0.15
AFF_Q_RATE_WARN = 0.40         # frazione messaggi: affermazione + domanda finale
AFF_Q_RATE_CRIT = 0.65
LENGTH_RATIO_WARN = 2.0        # agent words / user words (average)
LENGTH_RATIO_CRIT = 3.0
EMOJI_MONO_WARN = 0.50         # frazione emoji totali che sono l'emoji top-1
EMOJI_MONO_CRIT = 0.75

SAMPLE_N = 8  # messaggi peggiori inclusi nel report per il reviewer
LOOKBACK_DAYS = 7

# ── Pattern regex ─────────────────────────────────────────────────────────────

_BOT_PATTERNS = [
    r"\bcertamente\b",
    r"\bassolutamente\b",
    r"\bcome posso aiutarti\b",
    r"\bposso aiutarti\b",
    r"^\s*ecco[,!:\s]",
    r"\bottima domanda\b",
    r"\bcon piacere\b",
    r"\bsono qui per\b",
    r"\bnon esitare\b",
    r"\bfammi sapere\b",
    r"\bspero di esserti stat[ao]\b",
]
BOT_PHRASE_RE = re.compile("|".join(_BOT_PATTERNS), re.I | re.M)

BULLET_RE = re.compile(r"^\s*[-•*]\s+|\d+\.\s+", re.M)

EMOJI_RE = re.compile(
    r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF"
    r"\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U0001F900-\U0001F9FF"
    r"\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\U00002600-\U000026FF]"
)


# ── Logging ───────────────────────────────────────────────────────────────────

def _log(level: str, event: str, **kv: Any) -> None:
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "script": SCRIPT,
        "event": event,
        **kv,
    }
    print(json.dumps(payload), flush=True)


# ── Caricamento sessioni ──────────────────────────────────────────────────────

def _extract_text(content: Any) -> str:
    if isinstance(content, list):
        return " ".join(
            c.get("text", "") for c in content
            if isinstance(c, dict) and c.get("type") == "text"
        )
    return str(content) if content else ""


def load_recent_agent_sessions(
    profile_dir: Path, days: int = LOOKBACK_DAYS
) -> list[dict[str, str]]:
    """Restituisce lista di {'user': ..., 'agent': ..., 'session': ...} dagli ultimi N giorni."""
    sessions_dir = profile_dir / "sessions"
    if not sessions_dir.exists():
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    pairs: list[dict[str, str]] = []

    for fpath in sorted(sessions_dir.glob("*.jsonl")):
        try:
            date_str = fpath.name[:8]
            file_date = datetime.strptime(date_str, "%Y%m%d").replace(tzinfo=timezone.utc)
            if file_date < cutoff:
                continue
        except ValueError:
            continue

        current_user: str | None = None
        with open(fpath, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue

                role = msg.get("role")
                if role not in ("user", "assistant"):
                    continue

                text = _extract_text(msg.get("content", "")).strip()
                if not text:
                    continue

                if role == "user":
                    current_user = text
                elif role == "assistant" and current_user is not None:
                    if not text.startswith("[CONTEXT COMPACTION"):
                        pairs.append({
                            "user": current_user,
                            "agent": text,
                            "session": fpath.name,
                        })
                    current_user = None

    return pairs


# ── Metriche ─────────────────────────────────────────────────────────────────

def _is_aff_q(msg: str) -> bool:
    """True se il messaggio segue il pattern: affermazione poi domanda finale."""
    msg = msg.strip()
    if len(msg) < 50 or not msg.endswith("?"):
        return False
    before_q = msg[: msg.rfind("?")]
    return bool(re.search(r"[.!\n]", before_q))


def score_bot_patterns(pairs: list[dict[str, str]]) -> dict[str, Any]:
    """Calcola le 6 metriche di rilevamento pattern bot."""
    if not pairs:
        return {"error": "no_messages"}

    agent_msgs = [p["agent"] for p in pairs]
    user_msgs = [p["user"] for p in pairs]
    n = len(agent_msgs)

    total_chars = sum(len(m) for m in agent_msgs) or 1

    # Em dash
    emdash_count = sum(m.count("—") for m in agent_msgs)
    emdash_rate = round(emdash_count / total_chars * 100, 4)

    # Bullet point
    bullet_msgs = sum(1 for m in agent_msgs if BULLET_RE.search(m))
    bullet_rate = round(bullet_msgs / n, 4)

    # Frasi da chatbot
    bot_msgs = sum(1 for m in agent_msgs if BOT_PHRASE_RE.search(m))
    bot_phrase_rate = round(bot_msgs / n, 4)

    # Affermazione → domanda
    aff_q_msgs = sum(1 for m in agent_msgs if _is_aff_q(m))
    aff_q_rate = round(aff_q_msgs / n, 4)

    # Rapporto lunghezza
    agent_words = [len(m.split()) for m in agent_msgs]
    user_words = [max(1, len(m.split())) for m in user_msgs]
    ratios = [g / u for g, u in zip(agent_words, user_words)]
    avg_length_ratio = round(sum(ratios) / n, 2)

    # Monotonia emoji
    all_emojis = []
    for m in agent_msgs:
        all_emojis.extend(EMOJI_RE.findall(m))

    if all_emojis:
        counts = Counter(all_emojis)
        top1_count = counts.most_common(1)[0][1]
        top_emoji = counts.most_common(1)[0][0]
        emoji_mono = round(top1_count / len(all_emojis), 4)
    else:
        emoji_mono = 0.0
        top_emoji = ""

    return {
        "n_messages": n,
        "emdash_rate": emdash_rate,
        "emdash_count": emdash_count,
        "bullet_rate": bullet_rate,
        "bullet_msgs": bullet_msgs,
        "bot_phrase_rate": bot_phrase_rate,
        "bot_msgs": bot_msgs,
        "aff_q_rate": aff_q_rate,
        "aff_q_msgs": aff_q_msgs,
        "avg_length_ratio": avg_length_ratio,
        "emoji_mono": emoji_mono,
        "top_emoji": top_emoji,
    }


def score_severity(metrics: dict[str, Any]) -> str:
    """Ritorna 'critical', 'degraded' o 'good'."""
    thresholds = [
        ("emdash_rate",      EMDASH_RATE_WARN,     EMDASH_RATE_CRIT),
        ("bullet_rate",      BULLET_RATE_WARN,      BULLET_RATE_CRIT),
        ("bot_phrase_rate",  BOT_PHRASE_RATE_WARN,  BOT_PHRASE_RATE_CRIT),
        ("aff_q_rate",       AFF_Q_RATE_WARN,       AFF_Q_RATE_CRIT),
        ("avg_length_ratio", LENGTH_RATIO_WARN,     LENGTH_RATIO_CRIT),
        ("emoji_mono",       EMOJI_MONO_WARN,       EMOJI_MONO_CRIT),
    ]
    crits = sum(1 for k, _, c in thresholds if metrics.get(k, 0) >= c)
    warns = sum(1 for k, w, c in thresholds if w <= metrics.get(k, 0) < c)

    if crits >= 2:
        return "critical"
    if crits >= 1 or warns >= 2:
        return "degraded"
    return "good"


# ── Selezione campione per reviewer ──────────────────────────────────────────

def _bot_score(msg: str) -> float:
    score = 0.0
    score += msg.count("—") * 2.0
    if BULLET_RE.search(msg):
        score += 3.0
    if BOT_PHRASE_RE.search(msg):
        score += 3.0
    if _is_aff_q(msg):
        score += 2.0
    score += min(3.0, len(msg.split()) / 40.0)
    return score


def select_worst_samples(
    pairs: list[dict[str, str]], n: int = SAMPLE_N
) -> list[dict[str, str]]:
    """Restituisce i messaggi più bot-like per la valutazione qualitativa."""
    scored = sorted(pairs, key=lambda p: -_bot_score(p["agent"]))
    return scored[:n]


# ── Report ────────────────────────────────────────────────────────────────────

def _fmt_pct(v: float) -> str:
    return f"{v * 100:.1f}%"


def format_report(
    metrics: dict[str, Any],
    samples: list[dict[str, str]],
    severity: str,
) -> str:
    today = datetime.now(timezone.utc).date().isoformat()
    status = {"critical": "CRITICAL", "degraded": "DEGRADED", "good": "OK"}[severity]
    top_emoji = metrics.get("top_emoji", "")
    top_emoji_note = f" (top emoji: {top_emoji})" if top_emoji else ""

    lines = [
        f"## Relic Humanness Monitor — {today}",
        f"**Status**: {status}",
        "",
        "### Pattern Metrics (ultimi 7 giorni)",
        "| Metrica | Valore | Warn | Crit |",
        "|---------|--------|------|------|",
        f"| Em dash (per 100 char) | {metrics['emdash_rate']:.3f} | >{EMDASH_RATE_WARN} | >{EMDASH_RATE_CRIT} |",
        f"| Bullet point | {_fmt_pct(metrics['bullet_rate'])} | >{_fmt_pct(BULLET_RATE_WARN)} | >{_fmt_pct(BULLET_RATE_CRIT)} |",
        f"| Frasi chatbot | {_fmt_pct(metrics['bot_phrase_rate'])} | >{_fmt_pct(BOT_PHRASE_RATE_WARN)} | >{_fmt_pct(BOT_PHRASE_RATE_CRIT)} |",
        f"| Afferm.→domanda | {_fmt_pct(metrics['aff_q_rate'])} | >{_fmt_pct(AFF_Q_RATE_WARN)} | >{_fmt_pct(AFF_Q_RATE_CRIT)} |",
        f"| Lunghezza ratio (agent/user) | {metrics['avg_length_ratio']:.2f}x | >{LENGTH_RATIO_WARN}x | >{LENGTH_RATIO_CRIT}x |",
        f"| Emoji monotonia{top_emoji_note} | {_fmt_pct(metrics['emoji_mono'])} | >{_fmt_pct(EMOJI_MONO_WARN)} | >{_fmt_pct(EMOJI_MONO_CRIT)} |",
        "",
        f"_(N={metrics['n_messages']} messaggi analizzati)_",
        "",
    ]

    if samples:
        lines += [
            "### Campione per valutazione qualitativa (LLM-as-judge)",
            "",
            "**Rubrica reviewer** — valuta ogni messaggio su 4 dimensioni (1–5):",
            "- **Naturale**: sembra scritto da una persona vera, non da un sistema",
            "- **Proporzionato**: lunghezza e tono adeguati al messaggio ricevuto",
            "- **Continuo**: tiene il filo di ciò che è stato detto prima",
            "- **Diretto**: non cerca forzatamente di aiutare o risolvere",
            "",
            "Segnali negativi: `—`, bullet point, domanda finale obbligatoria, "
            "frasi da chatbot, tono da coach, risposta più lunga del necessario.",
            "",
        ]
        for i, p in enumerate(samples, 1):
            user_preview = p["user"][:200].replace("\n", " ")
            agent_preview = p["agent"][:400].replace("\n", " ")
            lines += [
                f"#### Scambio {i}",
                f"**User**: {user_preview}",
                f"**Agent**: {agent_preview}",
                "",
            ]

    lines += [
        "### Interventi raccomandati",
        "- Em dash elevato → aggiungere `—` a `forbidden_phrases` in humanness_overrides.json",
        "- Bullet elevato → `no_bullet_points: true`",
        "- Aff→domanda elevato → `no_mandatory_question: true`",
        "- Length ratio elevato → abbassare `max_response_chars`",
        "- Qualità qualitativa insufficiente → aggiornare la config stile agente o aggiungere stile overlay",
    ]

    return "\n".join(lines)


# ── Remediation ───────────────────────────────────────────────────────────────

def apply_remediation(metrics: dict[str, Any], severity: str) -> None:
    """Scrive humanness_overrides.json per calibrare il prompt builder di Hermes.

    Il file viene letto da prompt_builder.py a ogni sessione e inietta
    vincoli di stile in coda al system prompt.
    """
    if severity == "good":
        if HUMANNESS_OVERRIDES_FILE.exists():
            from relic.relic_override_store import snapshot_before_write
            snapshot_before_write(HUMANNESS_OVERRIDES_FILE, "humanness", RELIC_DIR)
            HUMANNESS_OVERRIDES_FILE.unlink()
            _log("INFO", "humanness_remediation_cleared", reason="patterns_within_threshold")
        return

    forbidden: list[str] = []
    if metrics.get("emdash_rate", 0) >= EMDASH_RATE_WARN:
        forbidden.append("—")
    if metrics.get("bot_phrase_rate", 0) >= BOT_PHRASE_RATE_WARN:
        forbidden.extend([
            "Certamente", "Assolutamente", "Ecco,", "Ecco!",
            "Come posso aiutarti", "Non esitare", "Fammi sapere",
            "Spero di esserti stat",
        ])

    overrides: dict[str, Any] = {
        "severity": severity,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=25)).isoformat(),
    }

    if forbidden:
        overrides["forbidden_phrases"] = forbidden
    if metrics.get("bullet_rate", 0) >= BULLET_RATE_WARN:
        overrides["no_bullet_points"] = True
    if metrics.get("aff_q_rate", 0) >= AFF_Q_RATE_WARN:
        overrides["no_mandatory_question"] = True
    if metrics.get("emoji_mono", 0) >= EMOJI_MONO_WARN:
        overrides["emoji_cap"] = 1
    if metrics.get("avg_length_ratio", 0) >= LENGTH_RATIO_WARN:
        overrides["max_response_chars"] = 350

    RELIC_DIR.mkdir(parents=True, exist_ok=True)
    from relic.relic_override_store import snapshot_before_write
    snapshot_before_write(HUMANNESS_OVERRIDES_FILE, "humanness", RELIC_DIR)
    HUMANNESS_OVERRIDES_FILE.write_text(json.dumps(overrides, indent=2, ensure_ascii=False))
    _log("INFO", "humanness_remediation_applied",
         severity=severity, active_constraints=list(overrides.keys()))


# ── Paperclip submission ──────────────────────────────────────────────────────


def _export_to_workspace(samples: list[dict[str, str]], metrics: dict, debate: dict) -> None:
    """Esporta campioni reali, metriche e dibattito nel workspace del reviewer."""
    reviewer_id = os.environ.get("PAPERCLIP_HUMANNESS_REVIEWER_ID", "")
    ws_root = Path(
        os.environ.get(
            "PAPERCLIP_WORKSPACE_ROOT",
            str(Path.home() / ".paperclip" / "instances" / "default" / "workspaces"),
        )
    )
    # Scrivi sample_agent_messages.md separatamente (formato markdown leggibile)
    if reviewer_id:
        ws = ws_root / reviewer_id
        if ws.exists():
            today = datetime.now(timezone.utc).date().isoformat()
            n = len(samples)
            out_lines = [
                "# Campioni messaggi agente relazionale",
                f"_Aggiornato: {today} — {n} scambi con pattern bot-like più elevato (ultimi 7 giorni)_",
                "",
            ]
            for i, p in enumerate(samples, 1):
                user_text = p["user"].replace("\n", " ")[:300]
                agent_text = p["agent"].replace("\n", " ")[:500]
                out_lines += [
                    f"## Scambio {i}",
                    f"**User**: {user_text}",
                    "",
                    f"**Agent**: {agent_text}",
                    "",
                ]
            (ws / "sample_agent_messages.md").write_text(
                "\n".join(out_lines), encoding="utf-8"
            )
    export_debate(
        reviewer_id=reviewer_id,
        debate=debate,
        extra_files={"humanness_metrics": metrics},
    )


def submit_paperclip_issue(
    report: str, severity: str, metrics: dict[str, Any], debate: dict
) -> None:
    api_url = os.environ.get("PAPERCLIP_API_URL", "http://localhost:3100")
    company_id = os.environ.get("PAPERCLIP_COMPANY_ID", "")
    api_key = os.environ.get("PAPERCLIP_HUMANNESS_ANALYST_KEY", "")
    reviewer_id = os.environ.get("PAPERCLIP_HUMANNESS_REVIEWER_ID", "")

    if not company_id or not api_key:
        _log("INFO", "paperclip_skip", reason="env vars not configured")
        return

    today = datetime.now(timezone.utc).date().isoformat()
    title = (
        f"[{today}] Humanness {severity.upper()} — "
        f"em_dash={metrics.get('emdash_rate', 0):.3f} "
        f"bullet={_fmt_pct(metrics.get('bullet_rate', 0))} "
        f"aff_q={_fmt_pct(metrics.get('aff_q_rate', 0))}"
    )

    debate_md = (
        f"\n\n---\n## Internal Debate (Pro/Contra/Judge)\n\n"
        f"**Pro** ({debate.get('pro', {}).get('model', '?')}):\n"
        f"{debate.get('pro', {}).get('argument', '')}\n\n"
        f"**Contra** ({debate.get('contra', {}).get('model', '?')}):\n"
        f"{debate.get('contra', {}).get('argument', '')}\n\n"
        f"**Judge verdict**: {debate.get('judge', {}).get('verdict', '?')} "
        f"(confidence={debate.get('judge', {}).get('confidence', 0):.2f})\n"
        f"{debate.get('judge', {}).get('rationale', '')}"
    )
    full_description = report + debate_md
    payload: dict[str, Any] = {"title": title, "description": full_description}
    if reviewer_id:
        payload["assigneeAgentId"] = reviewer_id

    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{api_url}/api/companies/{company_id}/issues",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            issue = json.loads(r.read())
            _log("INFO", "paperclip_issue_created",
                 id=issue.get("id", "?")[:8], severity=severity)
    except urllib.error.HTTPError as e:
        _log("WARN", "paperclip_http_error", code=e.code, body=e.read().decode()[:200])
    except Exception as exc:
        _log("WARN", "paperclip_error", error=str(exc))


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    if not HERMES_PROFILE_DIR or not HERMES_PROFILE_DIR.exists():
        _log("WARN", "hermes_profile_not_found",
             path=str(HERMES_PROFILE_DIR),
             hint="Set HERMES_PROFILE_DIR to the Hermes profile dir of the relational agent")
        return 1

    pairs = load_recent_agent_sessions(HERMES_PROFILE_DIR, days=LOOKBACK_DAYS)
    if not pairs:
        _log("WARN", "no_sessions_found", days=LOOKBACK_DAYS,
             sessions_dir=str(HERMES_PROFILE_DIR / "sessions"))
        return 1

    metrics = score_bot_patterns(pairs)
    if "error" in metrics:
        _log("WARN", "metrics_error", **metrics)
        return 1

    severity = score_severity(metrics)
    _log("INFO", "humanness_metrics", severity=severity, **{
        k: v for k, v in metrics.items() if k != "top_emoji"
    })

    samples = select_worst_samples(pairs)
    report = format_report(metrics, samples, severity)

    if severity == "good":
        _log("INFO", "humanness_ok", msg="tutti i pattern entro soglia")
        return 0

    debate = run_debate(
        domain="humanness",
        raw_data={"samples": [{"agent": p["agent"][:200]} for p in samples]},
        metrics=metrics,
        report_text=report,
    )
    _export_to_workspace(samples, metrics, debate)
    submit_paperclip_issue(report, severity, metrics, debate)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
