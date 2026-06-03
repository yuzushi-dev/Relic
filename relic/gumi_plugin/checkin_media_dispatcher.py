"""Checkin media dispatcher, routes LLM output to appropriate media generators.

Handles text, voice, image, and music delivery after gate decision.

Stdout contract (subject-facing):
  - text branch: sanitized message text only
  - voice/image/music: empty, delivery happens via Telegram Bot API directly
  - ALL [WARN], [DRY-RUN], MEDIA: lines go to stderr only

Hermes reads stdout and may forward it to the subject chat; nothing
operator-facing must ever appear there.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone

from relic.gumi_plugin.media_state import record_media_delivery, record_outbound_delivery, record_sent_media_memory
from relic.gumi_plugin.image_gen import generate_checkin_image
from relic.gumi_plugin.tts import synthesize_checkin_audio
from relic.gumi_plugin.lyria import LyriaGenerator
from relic.gumi_plugin.output_sanitizer import sanitize_for_subject, strip_terminal_full_stops

_TRAILING_SYMBOL_RE = re.compile(
    r"(\s*(?:[\U0001F300-\U0001FAFF\u2600-\u27BF]\ufe0f?|\ufe0f)+\s*)$"
)

# Gate control tokens / bracketed headers that may prefix a message blob but are
# not subject-facing prose. Used to look past them when detecting questions.
_GATE_CONTROL_RE = re.compile(r"^(DELIVER|BLOCKED|NO_REPLY|SILENT)\b", re.IGNORECASE)


def _strip_gate_control_lines(text: str) -> str:
    """Drop leading gate-control/header lines so question detection sees the prose."""
    kept = [
        ln for ln in text.splitlines()
        if not _GATE_CONTROL_RE.match(ln.strip())
        and not (ln.strip().startswith("[") and ln.strip().endswith("]"))
    ]
    return "\n".join(kept).strip()


def ensure_checkin_question_mark(text: str) -> str:
    """Ensure check-in questions keep an explicit question mark.

    Some models generate a semantically interrogative sentence and end with an
    emoji instead of punctuation. Put the question mark before trailing emoji so
    voice/text/image branches all preserve the question contract.
    """
    stripped = text.rstrip()
    if not stripped or "?" in stripped:
        return text
    match = _TRAILING_SYMBOL_RE.search(stripped)
    if match:
        body = stripped[: match.start()].rstrip()
        return f"{body}?{match.group(1)}"
    return f"{stripped}?"


# Italian interrogative openers used to detect when a proactive/diegetic line is
# actually a question (so we only restore a dropped "?" on real questions and
# never turn a statement into one). One- and two-token openers.
_IT_INTERROGATIVE_OPENERS = frozenset(
    {
        "come", "cosa", "che", "chi", "dove", "quando", "perché", "perche",
        "quanto", "quanta", "quanti", "quante", "quale", "quali",
        "preferisci", "hai", "sei", "vuoi", "riesci", "pensi", "senti",
        "ti va", "ti funziona", "ti andrebbe", "ti capita", "secondo te",
        "che cosa", "com'è", "come va", "come stai",
    }
)


def _looks_interrogative(text: str) -> bool:
    """Heuristic: does this line read as an Italian question?

    True if it already carries a "?" anywhere, or it opens with a known
    interrogative word/phrase. Conservative on purpose, used to decide whether
    to restore a dropped question mark without inventing questions.
    """
    body = _TRAILING_SYMBOL_RE.sub("", _strip_gate_control_lines(text)).strip().lower()
    if not body:
        return False
    if "?" in body:
        return True
    tokens = body.split()
    if not tokens:
        return False
    first = tokens[0].strip(".,;:!")
    two = " ".join(tokens[:2]).strip(".,;:!")
    return first in _IT_INTERROGATIVE_OPENERS or two in _IT_INTERROGATIVE_OPENERS


def ensure_question_mark_if_interrogative(text: str) -> str:
    """Restore a dropped question mark only when the line reads as a question.

    Used for proactive re-engagement, whose questions are optional, unlike
    check-ins, where the question is mandatory and ``ensure_checkin_question_mark``
    applies unconditionally.
    """
    if not _looks_interrogative(text):
        return text
    return ensure_checkin_question_mark(text)


def clean_image_caption(caption: str) -> str:
    """Remove only trailing periods from image captions.

    The old cleanup removed all terminal punctuation, including ``?``. The
    intended style rule is only "no final full stop" on captions.
    """
    return strip_terminal_full_stops(caption.strip())


def parse_gate_output(llm_output: str) -> dict:
    """Parse gate output to extract media type and content.

    Returns dict with keys:
        tipo: "text"|"voice"|"image"|"music"
        testo: full content (for text/voice/music)
        caption: extracted caption line (for image)
        image_prompt: extracted image_prompt line (for image)
    """
    lines = llm_output.strip().split("\n")
    media_type = "text"
    content_lines = []
    caption = ""
    image_prompt = ""

    for line in lines:
        stripped = line.strip()
        low = stripped.lower()
        if low.startswith("tipo:"):
            media_type = stripped.split(":", 1)[1].strip().lower()
        elif low.startswith("ora:"):
            pass
        elif low.startswith("caption:"):
            caption = stripped.split(":", 1)[1].strip()
        elif low.startswith("image_prompt:"):
            image_prompt = stripped.split(":", 1)[1].strip()
        else:
            content_lines.append(stripped)

    testo = "\n".join(l for l in content_lines if l).strip()

    return {
        "tipo": media_type,
        "testo": testo,
        "caption": caption,
        "image_prompt": image_prompt,
    }


def _get_api_key() -> Optional[str]:
    """Get GEMINI_API_KEY from .env file in Hermes home."""
    hermes_home = os.environ.get("HERMES_HOME")
    if hermes_home:
        env_path = Path(hermes_home) / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if "=" in line:
                    key, val = line.split("=", 1)
                    if key.strip() == "GEMINI_API_KEY":
                        return val.strip()
    return os.environ.get("GEMINI_API_KEY")


def _load_env(hermes_home: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    env_path = hermes_home / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def _send_telegram_media(
    hermes_home: Path,
    media_path: Path,
    media_type: str,
    caption: str = "",
    title: str = "",
    performer: str = "",
) -> bool:
    """Send a media file to Telegram via Bot API.

    media_type: 'voice' | 'image' | 'music'
    - voice: no caption, no text, pure voice note
    - image: caption shown below photo (stripped of trailing punctuation)
    - music: title + performer set on audio player, no caption
    Returns True on success.
    """
    import urllib.request

    env = _load_env(hermes_home)
    bot_token = env.get("TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = env.get("TELEGRAM_HOME_CHANNEL") or env.get("TELEGRAM_ALLOWED_USERS")

    if not bot_token or not chat_id:
        print("[WARN] Missing TELEGRAM_BOT_TOKEN or chat_id, skipping Telegram delivery", file=sys.stderr)
        return False

    if not media_path.exists():
        print(f"[WARN] Media file not found: {media_path}", file=sys.stderr)
        return False

    _METHOD = {"voice": "sendVoice", "image": "sendPhoto", "music": "sendAudio"}
    _FIELD  = {"voice": "voice",     "image": "photo",     "music": "audio"}
    method = _METHOD.get(media_type, "sendDocument")
    field  = _FIELD.get(media_type, "document")

    url = f"https://api.telegram.org/bot{bot_token}/{method}"

    boundary = "ReLiCboundary123"
    body_parts: list[bytes] = []

    def _part(name: str, value: str) -> bytes:
        return (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{value}\r\n"
        ).encode()

    body_parts.append(_part("chat_id", str(chat_id)))

    # voice: no caption, no extra text
    if media_type == "image" and caption:
        clean_caption = clean_image_caption(caption)
        if clean_caption:
            body_parts.append(_part("caption", clean_caption[:1024]))

    if media_type == "music":
        # title from lyrics (first meaningful line), no caption
        if title:
            body_parts.append(_part("title", title[:64]))
        if performer:
            body_parts.append(_part("performer", performer[:64]))

    with open(media_path, "rb") as fh:
        file_data = fh.read()

    filename = media_path.name
    body_parts.append(
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
            f"Content-Type: application/octet-stream\r\n\r\n"
        ).encode() + file_data + b"\r\n"
    )
    body_parts.append(f"--{boundary}--\r\n".encode())

    body = b"".join(body_parts)

    try:
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode())
            if result.get("ok"):
                return True
            print(f"[WARN] Telegram API error: {result.get('description')}", file=sys.stderr)
            return False
    except Exception as exc:
        print(f"[WARN] Telegram delivery failed: {exc}", file=sys.stderr)
        return False


def _send_telegram_text(hermes_home: Path, text: str) -> bool:
    """Send a plain text message to Telegram via Bot API sendMessage.

    Returns True on success. Silently returns False if token/chat_id missing
    or on any network error.
    """
    import urllib.parse
    import urllib.request

    env = _load_env(hermes_home)
    bot_token = env.get("TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = env.get("TELEGRAM_HOME_CHANNEL") or env.get("TELEGRAM_ALLOWED_USERS")

    if not bot_token or not chat_id:
        return False
    if not text:
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": str(chat_id), "text": text[:4096]}).encode()
    try:
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            if result.get("ok"):
                return True
            print(f"[WARN] Telegram sendMessage error: {result.get('description')}", file=sys.stderr)
            return False
    except Exception as exc:
        print(f"[WARN] Telegram text delivery failed: {exc}", file=sys.stderr)
        return False


def _get_gumi_name(relic_subject_home: Path) -> str:
    """Resolve Gumi's display name.

    Source-of-truth order:
      1. gumi_background_profile.json display_name/agent_name
      2. provenance/identity_generation_log.json agent_name (set at provision)
    Falls back to "Gumi" only when no canonical name was ever recorded, older
    subjects (e.g. barbara) carry the name only in the provenance log because
    provisioning did not back-fill the background profile.
    """
    import json as _json

    bg_path = relic_subject_home / "gumi_background_profile.json"
    if bg_path.exists():
        try:
            bg = _json.loads(bg_path.read_text(encoding="utf-8"))
            name = bg.get("display_name") or bg.get("agent_name")
            if name:
                return name
        except Exception:
            pass

    prov_path = relic_subject_home / "provenance" / "identity_generation_log.json"
    if prov_path.exists():
        try:
            log = _json.loads(prov_path.read_text(encoding="utf-8"))
            name = log.get("agent_name")
            if name:
                return name
        except Exception:
            pass

    return "Gumi"


def _music_title_from_lyrics(caption: str) -> str:
    """Extract a short song title from the first lyric line."""
    import re
    # Strip timestamp prefix like "[0.0:2.9] " if present
    lines = [re.sub(r"^\[\d+\.\d+[:\d.]*\]\s*", "", l).strip() for l in caption.splitlines() if l.strip()]
    first = lines[0] if lines else ""
    # Capitalise, max 40 chars, no trailing punctuation
    title = re.sub(r"[.!?;:]+$", "", first).strip()
    return title[:40] if title else "Canzone di Gumi"


def _critic_block_reason(text: str) -> Optional[str]:
    """Run the delivery-time OutputCritic on subject-facing text.

    Returns a block reason when the manuscript's final language guardrail must
    suppress delivery (dependency/need claims, false physical experience,
    non-consensual disclosure pressure), else None. Fail-open: any critic error
    allows delivery so the runtime never blocks on the guardrail itself.
    """
    try:
        from relic.gumi_plugin.critic import OutputCritic

        verdict = OutputCritic().review(text or "")
        return None if verdict.allow else verdict.reason
    except Exception:
        return None


def _prose_block_reason(text: str, decision_type: str = "") -> Optional[str]:
    """Delivery-time prose-quality scorer (AI-tell detection).

    Observe-only by default: logs score + violations to stderr and returns None
    (never blocks). Hard block is opt-in via RELIC_PROSE_HARD_BLOCK=1, gated by
    a threshold not yet calibrated on real Italian Gumi output. Fail-open: any
    error allows delivery so the runtime never blocks on the scorer itself.
    """
    try:
        from relic.gumi_plugin.prose_critic import ProseCritic, log_calibration_sample

        def _truthy(name: str) -> bool:
            return os.environ.get(name, "").strip().lower() in {"1", "true", "yes"}

        hard = _truthy("RELIC_PROSE_HARD_BLOCK")
        verdict = ProseCritic(hard_block=hard).review(text or "")

        # Gemma LLM judge (opt-in): higher recall than the regex on Italian slop.
        # Synchronous + timeout-bounded; fine on this non-interactive cron path.
        gemma_score: int | None = None
        gemma_block = False
        if _truthy("RELIC_PROSE_GEMMA_JUDGE"):
            from relic.gumi_plugin.gemma_judge import judge_score
            gemma_score = judge_score(text or "")
            if gemma_score is not None:
                try:
                    cut = int(os.environ.get("RELIC_PROSE_GEMMA_CUT", "50"))
                except ValueError:
                    cut = 50
                gemma_block = hard and gemma_score < cut

        # Numeric-only calibration log (no text/hash) for threshold tuning.
        log_calibration_sample(
            verdict, text or "", decision_type=decision_type, gemma_score=gemma_score
        )
        if verdict.violations or gemma_score is not None:
            print(
                f"[dispatch] prose_critic score={verdict.score} "
                f"reason={verdict.reason} violations={','.join(verdict.violations)} "
                f"gemma={gemma_score}",
                file=sys.stderr,
            )
        if gemma_block:
            return f"prose:gemma_low_{gemma_score}"
        return None if verdict.allow else f"prose:{verdict.reason}"
    except Exception:
        return None


def _event_kind_for_decision_type(decision_type: str) -> str:
    if decision_type == "proactivity":
        return "proactive"
    return decision_type or "checkin"


def _record_delivered_decision_event(subject_id: str, decision_type: str) -> None:
    """Append a canonical delivered event after the Telegram API accepted delivery."""
    try:
        from relic.paths import get_relic_home

        now = datetime.now(timezone.utc).isoformat()
        event = {
            "decision": "DELIVER",
            "reason_codes": ["dispatch_delivered"],
            "subject_id": subject_id,
            "gumi_instance_id": subject_id,
            "hermes_profile_id": "",
            "target_id": None,
            "metadata": {"source": "checkin_media_dispatcher"},
            "created_at": now,
            "delivered_at": now,
            "decision_type": decision_type,
            "event_kind": _event_kind_for_decision_type(decision_type),
            "outcome_status": "delivered",
            "delivered": True,
        }
        path = get_relic_home() / "decision_events.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception as exc:
        print(f"[WARN] delivered decision event write failed: {exc}", file=sys.stderr)


def dispatch(
    llm_output: str,
    hermes_home: Path,
    relic_subject_home: Path,
    subject_id: str,
    dry_run: bool = False,
    force: bool = False,
    decision_type: str = "checkin",
) -> dict:
    """Dispatch media based on gate output.

    Args:
        llm_output: Raw LLM output from checkin_message
        hermes_home: Path to Hermes profile home
        relic_subject_home: Path to subject's relic home
        subject_id: Subject ID
        dry_run: If True, simulate without API calls

    Returns:
        {"tipo": str, "success": bool, "output": str}

    Stdout contract: only sanitized subject-facing text is printed.
    Voice/image/music deliver via Telegram Bot API, stdout stays empty.
    """
    parsed = parse_gate_output(llm_output)
    tipo = parsed["tipo"]
    testo = parsed["testo"]
    if tipo in {"text", "voice", "image"}:
        if decision_type == "checkin":
            # Check-ins always carry a question: enforce unconditionally.
            testo = ensure_checkin_question_mark(testo)
            if parsed.get("caption"):
                parsed["caption"] = ensure_checkin_question_mark(parsed["caption"])
        elif decision_type in {"proactivity", "diegetic"}:
            # Proactive/diegetic questions are optional: only restore a dropped
            # "?" when the line actually reads as a question, never invent one.
            testo = ensure_question_mark_if_interrogative(testo)
            if parsed.get("caption"):
                parsed["caption"] = ensure_question_mark_if_interrogative(parsed["caption"])

    # Delivery-time language guardrail: applies to every subject-facing branch
    # (text body, and the source text synthesized into voice/image/music) before
    # anything is sent or printed.
    block_reason = _critic_block_reason(testo)
    if block_reason:
        print(
            f"[dispatch] blocked by output critic: {block_reason}, silent drop",
            file=sys.stderr,
        )
        return {"tipo": tipo, "success": False, "reason": f"critic_blocked:{block_reason}"}

    # Delivery-time prose-quality scorer (observe-only unless RELIC_PROSE_HARD_BLOCK).
    prose_reason = _prose_block_reason(testo, decision_type=decision_type)
    if prose_reason:
        print(
            f"[dispatch] blocked by prose critic: {prose_reason}, silent drop",
            file=sys.stderr,
        )
        return {"tipo": tipo, "success": False, "reason": f"prose_blocked:{prose_reason}"}

    api_key = _get_api_key()

    if tipo == "text":
        safe = sanitize_for_subject(testo)
        if safe is None:
            print("[dispatch] text blocked by sanitizer, silent drop", file=sys.stderr)
            return {"tipo": "text", "success": False, "reason": "sanitized_empty"}
        if dry_run:
            print("[DRY-RUN] Text send skipped", file=sys.stderr)
            return {"tipo": "text", "success": True, "dry_run": True, "output": safe}
        print(safe)  # stdout: subject-facing text message
        delivered = _send_telegram_text(hermes_home, safe)
        if delivered:
            record_outbound_delivery(hermes_home, "telegram", "text")
            _record_delivered_decision_event(subject_id, decision_type)
        return {"tipo": "text", "success": True, "output": safe, "telegram_delivered": delivered}

    elif tipo == "voice":
        if dry_run:
            print("[DRY-RUN] Voice synthesis skipped", file=sys.stderr)
            return {"tipo": "voice", "success": True, "dry_run": True}

        if not api_key:
            print("[WARN] No GEMINI_API_KEY, skipping voice", file=sys.stderr)
            return {"tipo": "voice", "success": False, "reason": "no_api_key"}

        audio_path = synthesize_checkin_audio(
            text=testo,
            hermes_home=hermes_home,
            relic_subject_home=relic_subject_home,
            api_key=api_key,
        )
        record_media_delivery(hermes_home, "voice")
        delivered = _send_telegram_media(hermes_home, audio_path, "voice")
        if delivered:
            record_outbound_delivery(hermes_home, "telegram", "voice")
            _record_delivered_decision_event(subject_id, decision_type)
            _summary = testo.strip().replace("\n", " ")[:90]
            record_sent_media_memory(hermes_home, f"Ho mandato una nota vocale: «{_summary}»")
        status = "DELIVERED" if delivered else "LOCAL_ONLY"
        print(f"MEDIA:{audio_path} [{status}]", file=sys.stderr)
        # No stdout: voice delivered directly via Telegram Bot API
        return {"tipo": "voice", "success": True, "audio_path": str(audio_path), "telegram_delivered": delivered}

    elif tipo == "image":
        if dry_run:
            print("[DRY-RUN] Image generation skipped", file=sys.stderr)
            return {"tipo": "image", "success": True, "dry_run": True}

        if not api_key:
            print("[WARN] No GEMINI_API_KEY, skipping image", file=sys.stderr)
            return {"tipo": "image", "success": False, "reason": "no_api_key"}

        caption = parsed["caption"] or testo
        image_prompt = parsed["image_prompt"]

        if image_prompt:
            # Gumi wrote the image prompt: use it directly
            from relic.gumi_plugin.image_gen import generate_image, collect_reference_images
            from datetime import date
            import hashlib
            ref_images = collect_reference_images(relic_subject_home, "close_selfie")
            today = date.today()
            seed = int(hashlib.sha256(f"{subject_id}{today}".encode()).hexdigest(), 16) % 10000
            tmp_dir = hermes_home / "tmp" / "gumi-images"
            output_path = tmp_dir / f"checkin_{today.isoformat()}_{seed:04d}.jpg"
            image_path = generate_image(image_prompt, ref_images, output_path, api_key)
        else:
            # Fallback: no image_prompt from Gumi, generate via checkin pipeline
            from datetime import datetime as _dt
            hour = _dt.now().hour
            time_of_day = "morning" if 6 <= hour < 12 else "afternoon" if 12 <= hour < 18 else "evening" if 18 <= hour < 22 else "night"
            image_path = generate_checkin_image(
                hermes_home=hermes_home,
                relic_subject_home=relic_subject_home,
                api_key=api_key,
                time_of_day=time_of_day,
                subject_id=subject_id,
                context_hint=testo,
            )

        record_media_delivery(hermes_home, "image")
        delivered = _send_telegram_media(hermes_home, image_path, "image", caption=caption[:1024])
        if delivered:
            record_outbound_delivery(hermes_home, "telegram", "image")
            _record_delivered_decision_event(subject_id, decision_type)
            _cap = (caption or "").strip().replace("\n", " ")[:90]
            record_sent_media_memory(
                hermes_home,
                f"Ho mandato una mia foto: «{_cap}»" if _cap else "Ho mandato una mia foto",
            )
        status = "DELIVERED" if delivered else "LOCAL_ONLY"
        print(f"MEDIA:{image_path} [{status}]", file=sys.stderr)
        # No stdout: image + caption delivered directly via Telegram Bot API
        return {"tipo": "image", "success": True, "image_path": str(image_path), "caption": caption, "telegram_delivered": delivered}

    elif tipo == "music":
        if dry_run:
            print("[DRY-RUN] Music generation skipped", file=sys.stderr)
            return {"tipo": "music", "success": True, "dry_run": True}

        if not api_key:
            print("[WARN] No GEMINI_API_KEY, skipping music", file=sys.stderr)
            return {"tipo": "music", "success": False, "reason": "no_api_key"}

        lyria_prompt = testo
        if not lyria_prompt:
            return {"tipo": "music", "success": False, "reason": "empty_lyria_prompt"}

        generator = LyriaGenerator(
            hermes_home=hermes_home,
            relic_subject_home=relic_subject_home,
            api_key=api_key,
        )
        result = generator.generate_and_deliver(
            target=subject_id,
            lyria_prompt=lyria_prompt,
            dry_run=False,
            force=force,
        )

        if not result.get("success"):
            print("[WARN] Music generation failed", file=sys.stderr)
            return {"tipo": "music", "success": False, "reason": result.get("reason")}

        record_media_delivery(hermes_home, "music")
        caption = result.get("caption", "")
        media_file = result.get("audio_path", "")
        music_title = _music_title_from_lyrics(caption)
        performer = _get_gumi_name(relic_subject_home)
        delivered = _send_telegram_media(
            hermes_home, Path(media_file), "music",
            title=music_title, performer=performer,
        ) if media_file else False
        if delivered:
            record_outbound_delivery(hermes_home, "telegram", "music")
            _record_delivered_decision_event(subject_id, decision_type)
            _title = (music_title or "").strip()[:80]
            record_sent_media_memory(
                hermes_home,
                f"Ho condiviso un brano che ho buttato giù («{_title}»)" if _title
                else "Ho condiviso un brano che ho buttato giù",
            )
        status = "DELIVERED" if delivered else "LOCAL_ONLY"
        print(f"MEDIA:{media_file} [{status}] title={music_title!r}", file=sys.stderr)
        # No stdout: music delivered directly via Telegram Bot API
        return {"tipo": "music", "success": True, "audio_path": media_file, "caption": caption, "telegram_delivered": delivered}

    else:
        safe = sanitize_for_subject(testo)
        if safe is None:
            print("[dispatch] fallback text blocked by sanitizer, silent drop", file=sys.stderr)
            return {"tipo": "text", "success": False, "reason": "sanitized_empty"}
        if dry_run:
            print("[DRY-RUN] Fallback text send skipped", file=sys.stderr)
            return {"tipo": "text", "success": True, "dry_run": True, "output": safe}
        print(safe)  # stdout: subject-facing text message
        delivered = _send_telegram_text(hermes_home, safe)
        if delivered:
            record_outbound_delivery(hermes_home, "telegram", "text")
            _record_delivered_decision_event(subject_id, decision_type)
        return {"tipo": "text", "success": True, "output": safe, "telegram_delivered": delivered}


def main():
    """CLI entry point for checkin media dispatcher."""
    import argparse

    parser = argparse.ArgumentParser(description="Checkin media dispatcher")
    parser.add_argument("--llm-output", required=True, help="LLM output from checkin_message")
    parser.add_argument("--hermes-home", type=Path, help="Hermes profile home path")
    parser.add_argument("--subject-home", type=Path, help="Relic subject home path")
    parser.add_argument("--subject-id", required=True, help="Subject ID")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without API calls")
    parser.add_argument("--force", action="store_true", help="Bypass cooldowns (for testing)")

    args = parser.parse_args()

    # Get paths from environment if not provided
    hermes_home = args.hermes_home or Path(os.environ.get(
        "HERMES_HOME",
        f"{os.environ.get('HOME')}/.hermes/profiles/gumi-{args.subject_id}"
    ))
    relic_subject_home = args.subject_home or Path(os.environ.get(
        "RELIC_SUBJECT_HOME",
        f"{os.environ.get('HOME')}/.relic/subjects/{args.subject_id}"
    ))

    force = args.force or os.environ.get("RELIC_FORCE_MEDIA_TYPE", "") != ""
    dispatch(
        llm_output=args.llm_output,
        hermes_home=hermes_home,
        relic_subject_home=relic_subject_home,
        subject_id=args.subject_id,
        dry_run=args.dry_run,
        force=force,
    )


if __name__ == "__main__":
    main()
