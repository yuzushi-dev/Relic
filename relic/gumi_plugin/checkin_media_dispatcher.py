"""Checkin media dispatcher — routes LLM output to appropriate media generators.

Handles text, voice, image, and music delivery after gate decision.

Stdout contract (subject-facing):
  - text branch: sanitized message text only
  - voice/image/music: empty — delivery happens via Telegram Bot API directly
  - ALL [WARN], [DRY-RUN], MEDIA: lines go to stderr only

Hermes reads stdout and may forward it to the subject chat; nothing
operator-facing must ever appear there.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional

from relic.gumi_plugin.media_state import record_media_delivery, record_outbound_delivery
from relic.gumi_plugin.image_gen import generate_checkin_image
from relic.gumi_plugin.tts import synthesize_checkin_audio
from relic.gumi_plugin.lyria import LyriaGenerator
from relic.gumi_plugin.output_sanitizer import sanitize_for_subject


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
    - voice: no caption, no text — pure voice note
    - image: caption shown below photo (stripped of trailing punctuation)
    - music: title + performer set on audio player, no caption
    Returns True on success.
    """
    import urllib.request

    env = _load_env(hermes_home)
    bot_token = env.get("TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = env.get("TELEGRAM_HOME_CHANNEL") or env.get("TELEGRAM_ALLOWED_USERS")

    if not bot_token or not chat_id:
        print("[WARN] Missing TELEGRAM_BOT_TOKEN or chat_id — skipping Telegram delivery", file=sys.stderr)
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
        # Strip trailing punctuation except commas; keep clean
        import re
        clean_caption = re.sub(r"[.!?;:]+$", "", caption.strip())
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
    """Read Gumi's display name from background profile."""
    bg_path = relic_subject_home / "gumi_background_profile.json"
    if bg_path.exists():
        try:
            import json as _json
            bg = _json.loads(bg_path.read_text(encoding="utf-8"))
            return bg.get("display_name") or bg.get("agent_name") or "Gumi"
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


def dispatch(
    llm_output: str,
    hermes_home: Path,
    relic_subject_home: Path,
    subject_id: str,
    dry_run: bool = False,
    force: bool = False,
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
    Voice/image/music deliver via Telegram Bot API — stdout stays empty.
    """
    parsed = parse_gate_output(llm_output)
    tipo = parsed["tipo"]
    testo = parsed["testo"]

    # Delivery-time language guardrail: applies to every subject-facing branch
    # (text body, and the source text synthesized into voice/image/music) before
    # anything is sent or printed.
    block_reason = _critic_block_reason(testo)
    if block_reason:
        print(
            f"[dispatch] blocked by output critic: {block_reason} — silent drop",
            file=sys.stderr,
        )
        return {"tipo": tipo, "success": False, "reason": f"critic_blocked:{block_reason}"}

    api_key = _get_api_key()

    if tipo == "text":
        safe = sanitize_for_subject(testo)
        if safe is None:
            print("[dispatch] text blocked by sanitizer — silent drop", file=sys.stderr)
            return {"tipo": "text", "success": False, "reason": "sanitized_empty"}
        print(safe)  # stdout: subject-facing text message
        delivered = _send_telegram_text(hermes_home, safe)
        if delivered:
            record_outbound_delivery(hermes_home, "telegram", "text")
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
            # Gumi wrote the image prompt — use it directly
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
        status = "DELIVERED" if delivered else "LOCAL_ONLY"
        print(f"MEDIA:{media_file} [{status}] title={music_title!r}", file=sys.stderr)
        # No stdout: music delivered directly via Telegram Bot API
        return {"tipo": "music", "success": True, "audio_path": media_file, "caption": caption, "telegram_delivered": delivered}

    else:
        safe = sanitize_for_subject(testo)
        if safe is None:
            print("[dispatch] fallback text blocked by sanitizer — silent drop", file=sys.stderr)
            return {"tipo": "text", "success": False, "reason": "sanitized_empty"}
        print(safe)  # stdout: subject-facing text message
        delivered = _send_telegram_text(hermes_home, safe)
        if delivered:
            record_outbound_delivery(hermes_home, "telegram", "text")
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
