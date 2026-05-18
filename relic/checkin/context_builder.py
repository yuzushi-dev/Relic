"""Context builder for Gumi proactive check-in delivery.

Extracted from render_no_agent_script() in gumi_plugin/cron_wiring.py.
All public functions are fail-open: exceptions return "" for that section.

Public API:
    build_deliver_context(subject_id, hermes_home, relic_home) -> str
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _load_consent(subject_id: str, relic_home: Path) -> bool:
    dp_path = relic_home / "subjects" / subject_id / "delivery_policy.json"
    if not dp_path.exists():
        return False
    try:
        dp = json.loads(dp_path.read_text(encoding="utf-8"))
        return bool(dp.get("consent_for_active_elicitation", False))
    except Exception as e:
        print(f"[checkin] delivery_policy load error: {e}", file=sys.stderr)
        return False


def build_recent_checkins_section(hermes_home: Path) -> str:
    """Parse MEMORY.md for recent checkin messages; return formatted block or ''."""
    try:
        mem_path = hermes_home / "MEMORY.md"
        if not mem_path.exists():
            return ""
        mem_text = mem_path.read_text(encoding="utf-8")

        checkin_job_id = None
        jobs_path = hermes_home / "cron" / "jobs.json"
        if jobs_path.exists():
            try:
                jobs_data = json.loads(jobs_path.read_text(encoding="utf-8"))
                for job in jobs_data.get("jobs", []):
                    jscript = (job.get("script") or "")
                    jname = (job.get("name") or "")
                    if "checkin" in jscript.lower() or "checkin_message" in jname.lower():
                        checkin_job_id = job.get("id")
                        break
            except Exception:
                pass

        block_re = re.compile(
            r"<!-- gumi:memory_sync:begin -->(.*?)<!-- gumi:memory_sync:end -->",
            re.DOTALL,
        )
        block_m = block_re.search(mem_text)
        recent_checkins: list[tuple[str, str]] = []
        if block_m:
            block = block_m.group(1)
            header_re = re.compile(
                r"### (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) \(job=(.+?)\)"
            )
            parts = header_re.split(block)
            pi = 1
            while pi + 2 <= len(parts):
                ts_str, jid, body = parts[pi], parts[pi + 1], parts[pi + 2]
                pi += 3
                if checkin_job_id and not jid.startswith(checkin_job_id):
                    continue
                lines = [
                    line.strip()[2:]
                    for line in body.splitlines()
                    if line.strip().startswith("> ")
                ]
                text = " ".join(
                    line for line in lines if line and line != "[SILENT]"
                ).strip()
                if text:
                    recent_checkins.append((ts_str, text))

        if not recent_checkins:
            return ""

        out = ["", "--- messaggi recenti inviati (non ripetere immagini o temi già usati) ---"]
        for ts_str, msg in recent_checkins[-5:]:
            out.append(f"• [{ts_str}] {msg[:120]}")
        return "\n".join(out)
    except Exception:
        return ""


def build_observations_section(db_path: Path) -> str:
    """Query recent observations from relic.db; return formatted block or ''."""
    try:
        if not db_path.exists():
            return ""
        import sqlite3
        cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        conn = sqlite3.connect(
            f"file:{db_path}?mode=ro", uri=True, timeout=5.0
        )
        try:
            rows = conn.execute(
                """SELECT o.content
                   FROM observations o
                   WHERE o.source_type = 'checkin_reply'
                     AND o.created_at >= ?
                   ORDER BY o.created_at DESC
                   LIMIT 3""",
                (cutoff,),
            ).fetchall()
        finally:
            conn.close()

        if not rows:
            return ""

        out = ["", "--- cosa ho imparato di recente ---"]
        for (obs_c,) in rows:
            if obs_c:
                out.append(f"• {obs_c[:120]}")
        return "\n".join(out) if len(out) > 2 else ""
    except Exception as e:
        print(f"[checkin] observations: {e}", file=sys.stderr)
        return ""


def build_topic_hint_section(subject_id: str, db_path: Path, bl_path: Path) -> str:
    """Select topic facet, render hint, persist exchange; return block or ''."""
    try:
        if not db_path.exists():
            return ""
        import hashlib
        import sqlite3
        from relic.checkin.anti_repeat import AntiRepeatGate
        from relic.checkin.question_engine import select_facet
        from relic.checkin.topic_hint import render_topic_hint

        day_seed = (
            int(
                hashlib.sha256(
                    f"{subject_id}|checkin|{datetime.now(timezone.utc).date()}".encode()
                ).hexdigest(),
                16,
            )
            % (2**32)
        )

        topic_block = ""
        topic_facet_id = None
        topic_hint_text = None

        conn_t = None
        try:
            conn_t = sqlite3.connect(
                f"file:{db_path}?mode=ro", uri=True, timeout=5.0
            )
            sel = select_facet(
                conn_t,
                bl_path if bl_path.exists() else None,
                seed=day_seed,
            )
            if sel.get("status") == "ask_now":
                ar = AntiRepeatGate(conn_t, jaccard_threshold=0.60).check(
                    sel["question_hint"]
                )
                if not ar["duplicate"]:
                    try:
                        recent_q = [
                            r[0]
                            for r in conn_t.execute(
                                "SELECT question_text FROM checkin_exchanges "
                                "ORDER BY asked_at DESC LIMIT 10"
                            ).fetchall()
                            if r[0]
                        ]
                    except Exception:
                        recent_q = []
                    topic_block = render_topic_hint(sel["question_hint"], recent_q)
                    if topic_block:
                        topic_facet_id = sel["selected_facet"]
                        topic_hint_text = sel["question_hint"]
        finally:
            if conn_t is not None:
                conn_t.close()

        if not topic_block:
            return ""

        # RO conn closed above — safe to open RW without lock contention.
        # Inner try/except so connect/write errors never discard the rendered block.
        try:
            conn_rw = sqlite3.connect(str(db_path), timeout=5.0)
            try:
                conn_rw.execute(
                    "INSERT INTO checkin_exchanges "
                    "(facet_id, question_text, asked_at) VALUES (?, ?, ?)",
                    (topic_facet_id, topic_hint_text, datetime.now(timezone.utc).isoformat()),
                )
                conn_rw.commit()
            except Exception as e_ins:
                if "no such table" not in str(e_ins):
                    print(f"[checkin] persist: {e_ins}", file=sys.stderr)
            finally:
                conn_rw.close()
        except Exception as e_rw:
            print(f"[checkin] persist (connect failed): {e_rw}", file=sys.stderr)

        return f"\n{topic_block}"
    except Exception as e:
        print(f"[checkin] topic hint: {e}", file=sys.stderr)
        return ""


def build_style_hints_section(bl_path: Path) -> str:
    """Load subject_baseline.json and render style hints; return block or ''."""
    try:
        if not bl_path.exists():
            return ""
        from relic.checkin.style_hints import render_style_hints

        bl = json.loads(bl_path.read_text(encoding="utf-8"))
        style_block = render_style_hints(bl.get("interaction") or {})
        return f"\n{style_block}" if style_block else ""
    except Exception as e:
        print(f"[checkin] style hints: {e}", file=sys.stderr)
        return ""


def build_recent_subject_messages_section(
    hermes_home: Path, hours: int = 24, limit: int = 5
) -> str:
    """Read role='user' messages from Hermes state.db; return formatted block or ''.

    Filters out cron task prompts (content starting with '[IMPORTANT:'),
    which are system-injected, not subject-authored.
    """
    try:
        db_path = hermes_home / "state.db"
        if not db_path.exists():
            return ""
        import sqlite3
        cutoff_ts = (datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp()
        conn = sqlite3.connect(
            f"file:{db_path}?mode=ro", uri=True, timeout=5.0
        )
        try:
            rows = conn.execute(
                """SELECT timestamp, content
                   FROM messages
                   WHERE role='user'
                     AND timestamp >= ?
                     AND content IS NOT NULL
                     AND content NOT LIKE '[IMPORTANT:%'
                   ORDER BY timestamp DESC
                   LIMIT ?""",
                (cutoff_ts, limit),
            ).fetchall()
        finally:
            conn.close()

        if not rows:
            return ""

        out = [
            "",
            "--- cosa ti ha detto di recente (ascoltalo, non parlare solo di te) ---",
        ]
        for ts, content in reversed(rows):
            try:
                dt_local = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone()
                ts_str = dt_local.strftime("%Y-%m-%d %H:%M")
            except Exception:
                ts_str = "?"
            text = content.strip()
            if text.startswith("[Replying to:"):
                # Keep the reply context but trim its quote bracket
                end_idx = text.find("]")
                if end_idx > 0 and end_idx < 250:
                    text = text[end_idx + 1 :].strip()
            out.append(f"• [{ts_str}] {text[:280]}")
        return "\n".join(out)
    except Exception as e:
        print(f"[checkin] subject messages: {e}", file=sys.stderr)
        return ""


def build_avatar_section(hermes_home: Path) -> str:
    """Read AVATAR_SPEC.md and return formatted block or ''."""
    try:
        avatar_path = hermes_home / "AVATAR_SPEC.md"
        if not avatar_path.exists():
            return ""
        avatar = avatar_path.read_text(encoding="utf-8").strip()
        if not avatar:
            return ""
        return f"\n--- aspetto di Gumi ---\n{avatar[:600]}"
    except Exception:
        return ""


def build_deliver_context(
    subject_id: str,
    hermes_home: Path | None,
    relic_home: Path | None = None,
) -> str:
    """Build context string for check-in DELIVER output.

    Sections emitted:
    1. Recent checkin messages from MEMORY.md (not consent-gated)
    2. Recent observations from relic.db (consent-gated)
    3. Topic hint + exchange INSERT (consent-gated)
    4. Style hints from subject_baseline.json (consent-gated)
    5. Avatar spec from AVATAR_SPEC.md (not consent-gated)

    All sections fail-open.
    """
    if not hermes_home:
        return ""

    if relic_home is None:
        import os

        relic_home = Path(
            os.environ.get("RELIC_HOME", "") or str(Path.home() / ".relic")
        )

    db_path = relic_home / "subjects" / subject_id / "relic.db"
    bl_path = relic_home / "subjects" / subject_id / "subject_baseline.json"

    consent = _load_consent(subject_id, relic_home)

    parts: list[str] = []

    parts.append(build_recent_checkins_section(hermes_home))
    parts.append(build_recent_subject_messages_section(hermes_home))

    if consent:
        parts.append(build_observations_section(db_path))
        parts.append(build_topic_hint_section(subject_id, db_path, bl_path))
        parts.append(build_style_hints_section(bl_path))

    parts.append(build_avatar_section(hermes_home))

    return "".join(part for part in parts if part)
