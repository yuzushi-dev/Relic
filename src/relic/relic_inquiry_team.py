#!/usr/bin/env python3
"""Relic Inquiry Team - adversarial multi-agent hypothesis verification.

Verifies cross-facet hypotheses before they enter the portrait layer (Layer 4).
A hypothesis is blocked from PORTRAIT.md until it passes the inquiry gate.

Pipeline per hypothesis:
  DeterministicRunner  (DB queries: temporal, cross-source, consistency)
        ↓  [skip if det_passed=False → inconclusive]
  ClaimDecomposer      (LLM: breaks hypothesis into falsifiable subclaims)
        ↓
  VerifierPro          (LLM-A: finds supporting evidence per subclaim)
  VerifierContra       (LLM-B: finds refuting evidence per subclaim)
        ↓
  EvidenceSynthesizer  (merges dossier, detects conflict)
        ↓
  ResolutionJudge      (verdict: verified/contested/inconclusive/needs_human)
        ↓
  [HumanReviewGate]    (Telegram full dossier if needs_human)

Verdict effects on hypotheses.status + confidence:
  verified      status='verified',      confidence += DELTA_VERIFIED   (cap 0.99)
  contested     status='contested',     confidence += DELTA_CONTESTED  (floor 0.05)
  inconclusive  status='inconclusive',  no confidence change
  needs_human   status='needs_human',   blocked, Telegram notification sent

Enable: RELIC_INQUIRY_TEAM=true
Cron:   relic:inquiry, daily at 04:00 (after relic:synthesize at 03:00)

Usage:
  python3 -m relic.relic_inquiry_team                    # new unverified hypotheses
  python3 -m relic.relic_inquiry_team --hypothesis-id 42
  python3 -m relic.relic_inquiry_team --all              # includes confirmed/legacy
  python3 -m relic.relic_inquiry_team --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import statistics
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib.llm_resilience import chat_completion_content
from lib.log import error, info, warn
from relic_db import (
    DB_PATH,
    get_db,
    get_hypotheses_for_inquiry,
    save_inquiry_case,
    save_inquiry_evidence,
    upsert_hypothesis,
)

SCRIPT = "relic_inquiry_team"
LLM_TIMEOUT = 120

# Deterministic thresholds
MIN_TEMPORAL_WEEKS = 3
MIN_SOURCE_TYPES = 2
MIN_CONSISTENCY = 0.30

# Confidence deltas applied after verdict
DELTA_VERIFIED = 0.05
DELTA_CONTESTED = -0.10

# Evidence retrieval caps
MAX_OBS_FOR_LLM = 30
MAX_EPISODES_FOR_LLM = 10

# LLM models (can override via env)
_DEFAULT_MODEL = os.environ.get("RELIC_INQUIRY_MODEL", "openrouter/openrouter/free")
_PRO_MODEL = os.environ.get("RELIC_INQUIRY_PRO_MODEL", _DEFAULT_MODEL)
_CONTRA_MODEL = os.environ.get(
    "RELIC_INQUIRY_CONTRA_MODEL",
    os.environ.get("RELIC_INQUIRY_MODEL", "openrouter/openrouter/free"),
)

# Telegram
_TG_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
_TG_CHAT = os.environ.get(
    "TELEGRAM_INQUIRY_CHAT_ID",
    os.environ.get("TELEGRAM_LOGS_CHAT_ID", ""),
)
_TG_THREAD = os.environ.get(
    "TELEGRAM_INQUIRY_THREAD_ID",
    os.environ.get("TELEGRAM_LOGS_THREAD_ID", ""),
)
_PAPERCLIP_WORKSPACE_ROOT = Path(
    os.environ.get(
        "PAPERCLIP_WORKSPACE_ROOT",
        str(Path.home() / ".paperclip" / "instances" / "default" / "workspaces"),
    )
)


# ── JSON helpers ─────────────────────────────────────────────────────────────

def _parse_json(raw: str) -> Any:
    s = raw.strip()
    if s.startswith("```"):
        lines = s.split("\n")
        s = "\n".join(lines[1:] if lines[0].startswith("```") else lines)
        if s.rstrip().endswith("```"):
            s = s.rstrip()[:-3].strip()
    m = re.search(r"\{[\s\S]*\}", s)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    raise ValueError(f"No parseable JSON in LLM response: {raw[:200]}")


# ── Telegram ─────────────────────────────────────────────────────────────────

def _send_telegram(text: str) -> None:
    if not _TG_TOKEN or not _TG_CHAT:
        warn(SCRIPT, "telegram_skip", reason="BOT_TOKEN or CHAT_ID not configured")
        return
    chunks = [text[i:i + 4000] for i in range(0, len(text), 4000)]
    for chunk in chunks:
        payload: dict[str, Any] = {
            "chat_id": _TG_CHAT,
            "text": chunk,
            "parse_mode": "HTML",
        }
        if _TG_THREAD:
            payload["message_thread_id"] = int(_TG_THREAD)
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{_TG_TOKEN}/sendMessage",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=15):
                pass
        except Exception as exc:
            warn(SCRIPT, "telegram_error", error=str(exc))


def _format_telegram_dossier(
    hypothesis: dict,
    subclaims: list[dict],
    pro_results: list[dict],
    contra_results: list[dict],
    det: dict,
    verdict: str,
    rationale: str,
) -> str:
    lines = [
        f"<b>🔍 Inquiry Team — needs_human</b>",
        f"<b>Hypothesis #{hypothesis['id']}</b>",
        f"<i>{hypothesis['hypothesis']}</i>",
        f"Confidence corrente: {hypothesis['confidence']:.2f}",
        "",
        "<b>Deterministic checks:</b>",
        f"  Temporal weeks: {det.get('temporal_weeks', '?')} (min {MIN_TEMPORAL_WEEKS}): {'✅' if det.get('temporal_ok') else '❌'}",
        f"  Source types: {det.get('source_types', '?')} (min {MIN_SOURCE_TYPES}): {'✅' if det.get('source_ok') else '❌'}",
        f"  Min consistency: {det.get('min_consistency', '?'):.2f} (min {MIN_CONSISTENCY}): {'✅' if det.get('consistency_ok') else '❌'}",
        "",
        "<b>Subclaims:</b>",
    ]
    for sc in subclaims:
        essential = "★" if sc.get("essential") else "·"
        lines.append(f"  {essential} [{sc['id']}] {sc['statement']}")

    lines += ["", "<b>Verifier-Pro (supporto):</b>"]
    for r in pro_results:
        ev_list = r.get("evidence", [])
        ev_str = "; ".join(
            f"{e.get('content','')[:80]} [{e.get('source_ref','')}] ({e.get('strength','')})"
            for e in ev_list[:2]
        )
        lines.append(f"  [{r['subclaim_id']}] {r['status']}: {ev_str or '—'}")

    lines += ["", "<b>Verifier-Contra (confutazione):</b>"]
    for r in contra_results:
        ev_list = r.get("evidence", [])
        ev_str = "; ".join(
            f"{e.get('content','')[:80]} [{e.get('source_ref','')}] ({e.get('strength','')})"
            for e in ev_list[:2]
        )
        lines.append(f"  [{r['subclaim_id']}] {r['status']}: {ev_str or '—'}")

    lines += [
        "",
        f"<b>Verdetto proposto:</b> {verdict}",
        f"<b>Rationale:</b> {rationale}",
        "",
        "Rispondi con: /approve_{hypothesis['id']} o /reject_{hypothesis['id']}",
    ]
    return "\n".join(lines)


# ── Evidence retrieval ────────────────────────────────────────────────────────

def _get_evidence_corpus(hypothesis: dict, conn: sqlite3.Connection) -> tuple[list[dict], list[str]]:
    """Return (observations, facet_ids) relevant to this hypothesis."""
    sup_ids: list[int] = []
    try:
        sup_ids = json.loads(hypothesis.get("supporting_observations") or "[]")
    except (json.JSONDecodeError, TypeError):
        pass

    facet_ids: list[str] = []
    if sup_ids:
        placeholders = ",".join("?" * len(sup_ids))
        rows = conn.execute(
            f"SELECT DISTINCT facet_id FROM observations WHERE id IN ({placeholders})",
            sup_ids,
        ).fetchall()
        facet_ids = [r[0] for r in rows]

    if not facet_ids:
        return [], []

    placeholders = ",".join("?" * len(facet_ids))
    obs_rows = conn.execute(
        f"""SELECT id, facet_id, source_type, source_ref, content, extracted_signal,
                   signal_strength, signal_position, created_at
            FROM observations
            WHERE facet_id IN ({placeholders}) AND signal_strength >= 0.4
            ORDER BY signal_strength DESC, created_at DESC
            LIMIT ?""",
        (*facet_ids, MAX_OBS_FOR_LLM),
    ).fetchall()
    return [dict(r) for r in obs_rows], facet_ids


def _get_episodes_excerpt(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """SELECT episode_type, content, source_ref, occurred_at
           FROM episodes WHERE active = 1
           ORDER BY occurred_at DESC LIMIT ?""",
        (MAX_EPISODES_FOR_LLM,),
    ).fetchall()
    return [dict(r) for r in rows]


# ── Deterministic Runner ──────────────────────────────────────────────────────

def _run_deterministic(
    facet_ids: list[str], conn: sqlite3.Connection
) -> dict[str, Any]:
    if not facet_ids:
        return {
            "passed": False,
            "temporal_weeks": 0,
            "temporal_ok": False,
            "source_types": 0,
            "source_ok": False,
            "min_consistency": 0.0,
            "consistency_ok": False,
            "reason": "no_facets_identified",
        }

    placeholders = ",".join("?" * len(facet_ids))

    # Check 1: temporal distribution
    week_rows = conn.execute(
        f"""SELECT DISTINCT strftime('%Y-%W', created_at) as week
            FROM observations
            WHERE facet_id IN ({placeholders}) AND signal_strength >= 0.4""",
        facet_ids,
    ).fetchall()
    temporal_weeks = len(week_rows)
    temporal_ok = temporal_weeks >= MIN_TEMPORAL_WEEKS

    # Check 2: cross-source agreement
    src_rows = conn.execute(
        f"""SELECT DISTINCT source_type FROM observations
            WHERE facet_id IN ({placeholders}) AND signal_strength >= 0.4""",
        facet_ids,
    ).fetchall()
    source_types = len(src_rows)
    source_ok = source_types >= MIN_SOURCE_TYPES

    # Check 3: consistency score of primary facets
    consistencies: list[float] = []
    for fid in facet_ids:
        pos_rows = conn.execute(
            """SELECT signal_position FROM observations
               WHERE facet_id = ? AND signal_position IS NOT NULL AND signal_strength >= 0.4""",
            (fid,),
        ).fetchall()
        positions = [r[0] for r in pos_rows if r[0] is not None]
        if len(positions) >= 2:
            try:
                consistency = max(0.1, 1.0 - statistics.stdev(positions))
            except statistics.StatisticsError:
                consistency = 0.1
            consistencies.append(consistency)

    min_consistency = min(consistencies) if consistencies else 0.0
    consistency_ok = min_consistency >= MIN_CONSISTENCY

    passed = temporal_ok and source_ok and consistency_ok

    return {
        "passed": passed,
        "temporal_weeks": temporal_weeks,
        "temporal_ok": temporal_ok,
        "source_types": source_types,
        "source_ok": source_ok,
        "min_consistency": round(min_consistency, 3),
        "consistency_ok": consistency_ok,
    }


# ── Claim Decomposer ──────────────────────────────────────────────────────────

def _decompose_claims(
    hypothesis_text: str,
    obs_excerpt: list[dict],
) -> list[dict]:
    obs_text = "\n".join(
        f"- [{o['source_type']}] {o.get('extracted_signal') or o['content'][:120]}"
        for o in obs_excerpt[:10]
    )
    prompt = f"""You are analyzing a behavioral/psychological hypothesis about a person.

Hypothesis: {hypothesis_text}

Sample supporting observations:
{obs_text}

Break this hypothesis into 3-5 falsifiable subclaims. Each subclaim must be:
- Individually testable against behavioral evidence
- Answerable as: supported | refuted | inconclusive
- Based on observable behavior, language patterns, or documented episodes
- Not a value judgment or clinical diagnosis

Return STRICT JSON only:
{{
  "subclaims": [
    {{"id": "c1", "statement": "...", "essential": true}},
    {{"id": "c2", "statement": "...", "essential": true}},
    {{"id": "c3", "statement": "...", "essential": false}}
  ]
}}"""

    try:
        content, _ = chat_completion_content(
            model=_DEFAULT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,
            temperature=0.2,
            timeout=LLM_TIMEOUT,
            title=SCRIPT,
        )
        parsed = _parse_json(content)
        return parsed.get("subclaims", [])
    except Exception as exc:
        warn(SCRIPT, "decomposer_error", error=str(exc))
        return [{"id": "c1", "statement": hypothesis_text, "essential": True}]


# ── Verifier Pro ──────────────────────────────────────────────────────────────

def _verify_pro(
    hypothesis_text: str,
    subclaims: list[dict],
    obs: list[dict],
    episodes: list[dict],
) -> list[dict]:
    obs_text = "\n".join(
        f"[{o['source_ref']}] [{o['source_type']}] strength={o['signal_strength']:.2f} | "
        f"{o.get('extracted_signal') or o['content'][:150]}"
        for o in obs
    )
    ep_text = "\n".join(
        f"[{e['source_ref']}] [{e['episode_type']}] {e['content'][:150]}"
        for e in episodes
    )
    sc_text = json.dumps(subclaims, ensure_ascii=False)

    prompt = f"""You are searching for EVIDENCE THAT SUPPORTS the following behavioral hypothesis.
Your task is to find concrete supporting evidence only. Do not challenge the hypothesis.

Hypothesis: {hypothesis_text}

Subclaims to verify:
{sc_text}

Behavioral observations:
{obs_text}

Episodic memory:
{ep_text}

For each subclaim, find the strongest supporting evidence. Cite exact source_ref values.
If evidence is absent for a subclaim, mark it inconclusive — do not fabricate.

Return STRICT JSON only:
{{
  "subclaim_results": [
    {{
      "subclaim_id": "c1",
      "status": "supported",
      "evidence": [
        {{"content": "...", "source_ref": "...", "strength": "weak|moderate|strong"}}
      ]
    }}
  ],
  "notes": "..."
}}"""

    try:
        content, _ = chat_completion_content(
            model=_PRO_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
            temperature=0.2,
            timeout=LLM_TIMEOUT,
            title=SCRIPT,
        )
        parsed = _parse_json(content)
        return parsed.get("subclaim_results", [])
    except Exception as exc:
        warn(SCRIPT, "verifier_pro_error", error=str(exc))
        return []


# ── Verifier Contra ───────────────────────────────────────────────────────────

def _verify_contra(
    hypothesis_text: str,
    subclaims: list[dict],
    obs: list[dict],
    episodes: list[dict],
) -> list[dict]:
    obs_text = "\n".join(
        f"[{o['source_ref']}] [{o['source_type']}] strength={o['signal_strength']:.2f} | "
        f"{o.get('extracted_signal') or o['content'][:150]}"
        for o in obs
    )
    ep_text = "\n".join(
        f"[{e['source_ref']}] [{e['episode_type']}] {e['content'][:150]}"
        for e in episodes
    )
    sc_text = json.dumps(subclaims, ensure_ascii=False)

    prompt = f"""You are challenging a behavioral hypothesis. Your task is to find concrete
COUNTER-EVIDENCE: exceptions, alternative explanations, temporal inconsistencies,
context-specific behaviors that contradict the general pattern.
Do NOT reject claims without concrete evidence from the record.

Hypothesis to challenge: {hypothesis_text}

Subclaims to challenge:
{sc_text}

Behavioral observations:
{obs_text}

Episodic memory:
{ep_text}

For each subclaim, find counter-evidence or mark inconclusive. Cite exact source_ref values.

Return STRICT JSON only:
{{
  "subclaim_results": [
    {{
      "subclaim_id": "c1",
      "status": "refuted",
      "evidence": [
        {{"content": "...", "source_ref": "...", "strength": "weak|moderate|strong"}}
      ]
    }}
  ],
  "notes": "..."
}}"""

    try:
        content, _ = chat_completion_content(
            model=_CONTRA_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
            temperature=0.2,
            timeout=LLM_TIMEOUT,
            title=SCRIPT,
        )
        parsed = _parse_json(content)
        return parsed.get("subclaim_results", [])
    except Exception as exc:
        warn(SCRIPT, "verifier_contra_error", error=str(exc))
        return []


# ── Evidence Synthesizer ──────────────────────────────────────────────────────

def _synthesize(
    subclaims: list[dict],
    pro_results: list[dict],
    contra_results: list[dict],
) -> tuple[list[dict], bool]:
    """Merge pro/contra per subclaim, detect conflict on essential subclaims."""
    pro_map = {r["subclaim_id"]: r for r in pro_results}
    contra_map = {r["subclaim_id"]: r for r in contra_results}
    conflict = False
    merged = []

    for sc in subclaims:
        sid = sc["id"]
        pro = pro_map.get(sid, {})
        contra = contra_map.get(sid, {})
        pro_status = pro.get("status", "inconclusive")
        contra_status = contra.get("status", "inconclusive")

        is_conflict = (
            sc.get("essential", True)
            and pro_status == "supported"
            and contra_status == "refuted"
        )
        if is_conflict:
            conflict = True

        merged.append({
            "subclaim_id": sid,
            "statement": sc.get("statement", ""),
            "essential": sc.get("essential", True),
            "pro_status": pro_status,
            "pro_evidence": pro.get("evidence", []),
            "contra_status": contra_status,
            "contra_evidence": contra.get("evidence", []),
            "conflict": is_conflict,
        })

    return merged, conflict


# ── Resolution Judge ──────────────────────────────────────────────────────────

def _judge(
    hypothesis_text: str,
    det: dict,
    merged: list[dict],
    conflict: bool,
) -> dict[str, Any]:
    dossier_text = json.dumps(merged, ensure_ascii=False, indent=2)
    det_text = (
        f"temporal_weeks={det['temporal_weeks']} (need {MIN_TEMPORAL_WEEKS}): {'PASS' if det['temporal_ok'] else 'FAIL'}\n"
        f"source_types={det['source_types']} (need {MIN_SOURCE_TYPES}): {'PASS' if det['source_ok'] else 'FAIL'}\n"
        f"min_consistency={det['min_consistency']:.2f} (need {MIN_CONSISTENCY}): {'PASS' if det['consistency_ok'] else 'FAIL'}"
    )

    prompt = f"""You are a Resolution Judge reviewing a hypothesis verification dossier.
You may ONLY reach a verdict based on the evidence below. Do not perform new research.

Hypothesis: {hypothesis_text}

Deterministic checks:
{det_text}

Evidence dossier (subclaims with pro/contra evidence):
{dossier_text}

Verdict rules:
- verified: all essential subclaims have pro_status='supported', no essential subclaim has strong contra, at least 1 strong evidence anchor
- contested: at least 1 essential subclaim has strong refuting evidence (contra_status='refuted' with strength='strong' or 'moderate')
- inconclusive: evidence incomplete, mixed but inconclusive, or below threshold
- needs_human: Pro and Contra conflict on an essential subclaim (conflict=true in dossier)

Return STRICT JSON only:
{{
  "verdict": "verified|contested|inconclusive|needs_human",
  "confidence_delta": <float between -0.15 and +0.08>,
  "rationale": "<1-2 sentences citing specific evidence>",
  "conflict": <true|false>
}}"""

    try:
        content, _ = chat_completion_content(
            model=_DEFAULT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=384,
            temperature=0.1,
            timeout=LLM_TIMEOUT,
            title=SCRIPT,
        )
        parsed = _parse_json(content)
        verdict = parsed.get("verdict", "inconclusive")
        if verdict not in ("verified", "contested", "inconclusive", "needs_human"):
            verdict = "inconclusive"
        delta = float(parsed.get("confidence_delta", 0.0))
        delta = max(-0.15, min(0.08, delta))
        return {
            "verdict": verdict,
            "confidence_delta": delta,
            "rationale": str(parsed.get("rationale", "")),
            "conflict": bool(parsed.get("conflict", conflict)),
        }
    except Exception as exc:
        warn(SCRIPT, "judge_error", error=str(exc))
        return {
            "verdict": "inconclusive",
            "confidence_delta": 0.0,
            "rationale": f"judge_error: {exc}",
            "conflict": conflict,
        }


# ── Main pipeline ─────────────────────────────────────────────────────────────

def run_inquiry(
    hypothesis: dict,
    conn: sqlite3.Connection,
    dry_run: bool = False,
) -> dict[str, Any]:
    h_id = hypothesis["id"]
    h_text = hypothesis["hypothesis"]
    case_id = str(uuid.uuid4())

    info(SCRIPT, "inquiry_start", hypothesis_id=h_id, text=h_text[:80])

    # Step 1: get relevant observations and facet_ids
    obs, facet_ids = _get_evidence_corpus(hypothesis, conn)
    episodes = _get_episodes_excerpt(conn)

    # Step 2: deterministic runner
    det = _run_deterministic(facet_ids, conn)
    info(SCRIPT, "deterministic_result", hypothesis_id=h_id, **{
        k: v for k, v in det.items() if k != "passed"
    }, passed=det["passed"])

    if not det["passed"]:
        verdict_data = {
            "verdict": "inconclusive",
            "confidence_delta": 0.0,
            "rationale": f"Deterministic checks failed: temporal={det['temporal_weeks']}wk source={det['source_types']}types consistency={det['min_consistency']:.2f}",
            "conflict": False,
        }
        subclaims: list[dict] = []
        pro_results: list[dict] = []
        contra_results: list[dict] = []
        merged: list[dict] = []
    else:
        # Step 3: claim decomposition
        subclaims = _decompose_claims(h_text, obs)
        info(SCRIPT, "subclaims_generated", hypothesis_id=h_id, count=len(subclaims))

        # Step 4: pro and contra (independent)
        pro_results = _verify_pro(h_text, subclaims, obs, episodes)
        contra_results = _verify_contra(h_text, subclaims, obs, episodes)

        # Step 5: synthesize
        merged, conflict = _synthesize(subclaims, pro_results, contra_results)

        # Step 6: judge
        verdict_data = _judge(h_text, det, merged, conflict)

    verdict = verdict_data["verdict"]
    delta = verdict_data["confidence_delta"]
    rationale = verdict_data["rationale"]
    conflict_flag = verdict_data["conflict"]
    requires_human = verdict == "needs_human"

    info(SCRIPT, "verdict", hypothesis_id=h_id, verdict=verdict,
         delta=delta, conflict=conflict_flag)

    if not dry_run:
        # Persist case
        save_inquiry_case(
            case_id=case_id,
            hypothesis_id=h_id,
            subclaims=subclaims,
            det_temporal_weeks=det["temporal_weeks"],
            det_source_types=det["source_types"],
            det_min_consistency=det["min_consistency"],
            det_passed=det["passed"],
            verdict=verdict,
            confidence_delta=delta,
            rationale=rationale,
            conflict=conflict_flag,
            requires_human=requires_human,
            conn=conn,
        )

        # Persist evidence items
        for r in pro_results:
            for ev in r.get("evidence", []):
                ev_id = str(uuid.uuid4())
                save_inquiry_evidence(
                    ev_id=ev_id,
                    case_id=case_id,
                    subclaim_id=r["subclaim_id"],
                    kind="supporting",
                    source_agent="verifier_pro",
                    content=str(ev.get("content", "")),
                    source_ref=str(ev.get("source_ref", "")),
                    strength=str(ev.get("strength", "")),
                    conn=conn,
                )
        for r in contra_results:
            for ev in r.get("evidence", []):
                ev_id = str(uuid.uuid4())
                save_inquiry_evidence(
                    ev_id=ev_id,
                    case_id=case_id,
                    subclaim_id=r["subclaim_id"],
                    kind="refuting",
                    source_agent="verifier_contra",
                    content=str(ev.get("content", "")),
                    source_ref=str(ev.get("source_ref", "")),
                    strength=str(ev.get("strength", "")),
                    conn=conn,
                )

        # Update hypothesis
        new_conf = hypothesis["confidence"]
        if verdict == "verified":
            new_conf = min(0.99, new_conf + DELTA_VERIFIED)
        elif verdict == "contested":
            new_conf = max(0.05, new_conf + DELTA_CONTESTED)

        upsert_hypothesis(
            hypothesis=h_text,
            status=verdict,
            confidence=new_conf,
            hypothesis_id=h_id,
            conn=conn,
        )
        conn.commit()

        # Human review notification
        if requires_human:
            msg = _format_telegram_dossier(
                hypothesis=hypothesis,
                subclaims=subclaims,
                pro_results=pro_results,
                contra_results=contra_results,
                det=det,
                verdict=verdict,
                rationale=rationale,
            )
            _send_telegram(msg)
            info(SCRIPT, "human_review_notified", hypothesis_id=h_id)

    return {
        "hypothesis_id": h_id,
        "case_id": case_id,
        "verdict": verdict,
        "confidence_delta": delta,
        "conflict": conflict_flag,
        "det_passed": det["passed"],
        "dry_run": dry_run,
    }


# ── Paperclip intake ──────────────────────────────────────────────────────────


def _export_to_workspace(results: list[dict], conn: "sqlite3.Connection") -> None:
    """Esporta hypotheses con testo completo nel workspace del reviewer."""
    reviewer_id = os.environ.get("PAPERCLIP_INQ_REVIEWER_ID", "")
    if not reviewer_id:
        return
    ws = _PAPERCLIP_WORKSPACE_ROOT / reviewer_id
    if not ws.exists():
        return

    h_ids = [r["hypothesis_id"] for r in results if "hypothesis_id" in r]
    if not h_ids:
        return

    placeholders = ",".join("?" * len(h_ids))
    rows = conn.execute(
        f"SELECT id, hypothesis, status, confidence, "
        f"supporting_observations, contradicting_observations "
        f"FROM hypotheses WHERE id IN ({placeholders})",
        h_ids,
    ).fetchall()

    batch = []
    for row in rows:
        h_id = row[0]
        result = next((r for r in results if r.get("hypothesis_id") == h_id), {})
        batch.append({
            "id": h_id,
            "hypothesis": row[1],
            "current_status": row[2],
            "confidence": row[3],
            "conflict": result.get("conflict", False),
        })

    (ws / "hypotheses_batch.json").write_text(
        json.dumps(batch, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    info(SCRIPT, f"workspace_exported reviewer={reviewer_id[:8]} hypotheses={len(batch)}")


def _submit_paperclip_inquiry_batch(results: list[dict]) -> None:
    """Submit inquiry batch results as a Paperclip issue for the Inquiry Reviewer."""
    api_url = os.environ.get("PAPERCLIP_API_URL", "http://localhost:3100")
    company_id = os.environ.get("PAPERCLIP_COMPANY_ID", "")
    api_key = os.environ.get("PAPERCLIP_INQ_ANALYST_KEY", "")
    reviewer_id = os.environ.get("PAPERCLIP_INQ_REVIEWER_ID", "")

    if not company_id or not api_key:
        return

    verdicts = [r["verdict"] for r in results]
    today = datetime.now(timezone.utc).date().isoformat()
    title = (
        f"[{today}] Inquiry batch — "
        f"{verdicts.count('verified')} verified, "
        f"{verdicts.count('contested')} contested, "
        f"{verdicts.count('needs_human')} needs_human"
    )

    rows = "\n".join(
        f"- h#{r['hypothesis_id']} case={r.get('case_id','?')} "
        f"conflict={r.get('conflict',False)}"
        for r in results
    )
    description = f"## Inquiry Verification Batch — {today}\n\n{rows}"

    payload: dict = {"title": title, "description": description}
    if reviewer_id:
        payload["assigneeId"] = reviewer_id

    import urllib.request as _urlreq, json as _json
    body = _json.dumps(payload).encode()
    req = _urlreq.Request(
        f"{api_url}/api/companies/{company_id}/issues",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    try:
        with _urlreq.urlopen(req, timeout=10) as r:
            issue = _json.loads(r.read())
            info(SCRIPT, f"paperclip_issue_created id={issue.get('id','?')[:8]}")
    except Exception as exc:
        warn(SCRIPT, "paperclip_issue_error", error=str(exc))


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> int:
    if os.environ.get("RELIC_INQUIRY_TEAM", "false").lower() not in ("true", "1", "yes"):
        print(json.dumps({
            "level": "warn",
            "script": SCRIPT,
            "event": "disabled",
            "message": "Set RELIC_INQUIRY_TEAM=true to enable",
        }))
        return 0

    parser = argparse.ArgumentParser(
        description="Relic Inquiry Team - adversarial hypothesis verification"
    )
    parser.add_argument("--hypothesis-id", type=int, help="Verify a single hypothesis by ID")
    parser.add_argument("--all", action="store_true",
                        help="Include legacy [confirmed] hypotheses (re-examine all)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Run pipeline without writing to DB or sending notifications")
    parser.add_argument("--db", help="Path to relic.db (default: from RELIC_DATA_DIR)")
    args = parser.parse_args()

    db_path = Path(args.db) if args.db else DB_PATH
    conn = get_db(db_path)
    conn.execute("PRAGMA journal_mode=WAL")

    try:
        if args.hypothesis_id:
            row = conn.execute(
                "SELECT * FROM hypotheses WHERE id = ?", (args.hypothesis_id,)
            ).fetchone()
            if not row:
                error(SCRIPT, "hypothesis_not_found", id=args.hypothesis_id)
                return 1
            hypotheses = [dict(row)]
        else:
            hypotheses = get_hypotheses_for_inquiry(
                include_legacy_confirmed=args.all,
                conn=conn,
            )

        if not hypotheses:
            info(SCRIPT, "nothing_to_verify")
            return 0

        info(SCRIPT, "batch_start", count=len(hypotheses), dry_run=args.dry_run)

        results = []
        for h in hypotheses:
            result = run_inquiry(h, conn=conn, dry_run=args.dry_run)
            results.append(result)
            print(json.dumps(result, ensure_ascii=False))

        verdicts = [r["verdict"] for r in results]
        info(SCRIPT, "batch_done",
             total=len(results),
             verified=verdicts.count("verified"),
             contested=verdicts.count("contested"),
             inconclusive=verdicts.count("inconclusive"),
             needs_human=verdicts.count("needs_human"))

        if not args.dry_run:
            _export_to_workspace(results, conn)
            _submit_paperclip_inquiry_batch(results)

        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
